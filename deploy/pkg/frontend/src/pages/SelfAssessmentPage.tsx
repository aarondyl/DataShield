import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { analyzeDocument, getQuestionnaire, listAssessments, runAssessment, uploadComplianceDocument } from '../api';
import { useProducts } from '../hooks';
import type { Assessment, ComplianceQuestion, Questionnaire } from '../types';
import ErrorBox from '../components/ErrorBox';
import PageHeader from '../components/PageHeader';
import Spinner from '../components/Spinner';

const inputCls = 'w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500';

const levelKeyMap: Record<string, string> = { 高: 'high', 中: 'medium', 低: 'low' };

function visible(question: ComplianceQuestion, answers: Record<string, unknown>) {
  return !question.show_if || answers[question.show_if.key] === question.show_if.equals;
}

function AssessmentResult({ result }: { result: Assessment }) {
  const { t } = useTranslation();
  const severity = { 高: 'bg-red-50 border-red-200 text-red-800', 中: 'bg-amber-50 border-amber-200 text-amber-800', 低: 'bg-emerald-50 border-emerald-200 text-emerald-800' };
  const download = () => {
    const blob = new Blob([result.report_markdown], { type: 'text/markdown;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `datashield-assessment-${result.id}.md`;
    link.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="space-y-5 mt-8">
      <div className="grid grid-cols-2 md:grid-cols-5 gap-3">
        <div className="bg-slate-900 text-white rounded-xl p-5 col-span-2"><div className="text-sm text-slate-300">{t('business.assessment.totalScore')}</div><div className="text-4xl font-bold mt-1">{result.score}</div><div className="text-sm mt-1">{result.rating}</div></div>
        {(['高', '中', '低'] as const).map((level) => <div key={level} className="bg-white border rounded-xl p-5"><div className="text-xs text-gray-500">{t(`business.assessment.riskCount.${levelKeyMap[level]}`)}</div><div className="text-3xl font-semibold mt-2">{result.counts[level] ?? 0}</div></div>)}
      </div>
      <section className="bg-white border rounded-xl p-5">
        <div className="flex justify-between items-center mb-4"><h2 className="font-semibold">{t('business.assessment.dimensionTitle')}</h2><button onClick={download} className="text-sm px-3 py-2 bg-indigo-600 text-white rounded-md">{t('business.assessment.downloadReport')}</button></div>
        <div className="space-y-3">{Object.entries(result.dimension_scores).map(([name, score]) => <div key={name} className="grid grid-cols-[110px_1fr_40px] items-center gap-3 text-sm"><span>{name}</span><div className="h-2 bg-gray-100 rounded-full"><div className="h-2 bg-indigo-500 rounded-full" style={{ width: `${score}%` }} /></div><span>{score}</span></div>)}</div>
      </section>
      <section className="space-y-3"><h2 className="font-semibold">{t('business.assessment.risksTitle')}</h2>{result.hits.map((hit) => <div key={hit.rule_id} className={`border rounded-xl p-4 ${severity[hit.level]}`}><div className="flex gap-2 items-center"><span className="font-semibold">{hit.rule_id}</span><span className="text-xs px-2 py-0.5 bg-white/70 rounded">{t('business.assessment.hitRisk', { dimension: hit.dimension, level: levelKeyMap[hit.level] ? t(`business.assessment.level.${levelKeyMap[hit.level]}`) : hit.level })}</span></div><p className="text-sm mt-2">{hit.risk}</p><p className="text-sm mt-2"><b>{t('business.assessment.adviceLabel')}</b>{hit.advice}</p><p className="text-xs mt-2 opacity-70">{t('business.assessment.relatedArticles', { articles: hit.articles.join(t('business.assessment.listSep')) })}</p></div>)}</section>
      <section className="bg-white border rounded-xl p-5"><h2 className="font-semibold mb-4">{t('business.assessment.roadmapTitle')}</h2><div className="grid grid-cols-1 lg:grid-cols-3 gap-4">{Object.entries(result.roadmap).map(([stage, items]) => <div key={stage} className="border rounded-lg p-4"><div className="font-medium text-sm">{stage}</div><div className="mt-3 space-y-2">{items.length ? items.map((item) => <label key={item.rule_id} className="flex gap-2 text-xs text-gray-700"><input type="checkbox" className="mt-0.5"/><span><b>{item.rule_id}</b> {item.advice}</span></label>) : <span className="text-xs text-gray-400">{t('business.assessment.noTasks')}</span>}</div></div>)}</div></section>
      {result.related_cases.length > 0 && <section className="bg-white border rounded-xl p-5"><h2 className="font-semibold mb-4">{t('business.assessment.casesTitle')}</h2><div className="grid grid-cols-1 md:grid-cols-2 gap-3">{result.related_cases.map((item) => <div key={item.name} className="border rounded-lg p-4"><div className="font-medium text-sm">{item.name}</div><div className="text-xs text-red-700 mt-1">{item.fine} · {item.authority}</div><p className="text-xs text-gray-600 mt-2">{item.lesson}</p></div>)}</div></section>}
    </div>
  );
}

export default function SelfAssessmentPage() {
  const { t } = useTranslation();
  const products = useProducts();
  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null);
  const [answers, setAnswers] = useState<Record<string, unknown>>({});
  const [productId, setProductId] = useState<number | ''>('');
  const [documentText, setDocumentText] = useState('');
  const [note, setNote] = useState('');
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<Assessment | null>(null);
  const [preset, setPreset] = useState('自定义填写');
  const [history, setHistory] = useState<Assessment[]>([]);

  useEffect(() => { getQuestionnaire().then((data) => { setQuestionnaire(data); setAnswers(Object.fromEntries(data.questions.map((q) => [q.key, q.default]))); }).catch((e) => setError(e.message)).finally(() => setLoading(false)); }, []);
  useEffect(() => { listAssessments().then(setHistory).catch(() => undefined); }, []);
  useEffect(() => { if (productId === '' && products.data?.length) setProductId(products.data[0].id); }, [products.data, productId]);
  useEffect(() => { const product=products.data?.find((p)=>p.id===productId); if(!product)return; setAnswers((a)=>({...a,collect_personal:product.collects_personal_data,collect_sensitive:product.collects_sensitive_data,minors_under_14:product.children_related,share_third_party:product.third_party_data_sharing||product.uses_third_party_sdk,privacy_policy:product.has_privacy_policy,storage_location:product.cross_border_data_transfer?'跨境传输到中国境外':a.storage_location})); }, [productId, products.data]);
  const grouped = useMemo(() => questionnaire ? questionnaire.modules.map((module) => ({ module, questions: questionnaire.questions.filter((q) => q.module === module && visible(q, answers)) })) : [], [questionnaire, answers]);

  const update = (key: string, value: unknown) => setAnswers((current) => ({ ...current, [key]: value }));
  const prefill = async () => { if (!documentText.trim()) return; setSubmitting(true); setError(null); try { const data = await analyzeDocument(documentText); setAnswers((a) => ({ ...a, ...data.suggestions })); setNote(data.note); } catch (e: any) { setError(e?.response?.data?.detail ?? e.message); } finally { setSubmitting(false); } };
  const upload = async (file?: File) => { if (!file) return; setSubmitting(true); setError(null); try { const data = await uploadComplianceDocument(file); setAnswers((a) => ({ ...a, ...data.suggestions })); setNote(data.note); } catch (e: any) { setError(e?.response?.data?.detail ?? e.message); } finally { setSubmitting(false); } };
  const submit = async () => { if (productId === '') { setError(t('business.assessment.errorNoProduct')); return; } setSubmitting(true); setError(null); try { const created = await runAssessment(productId, answers); setResult(created); setHistory((items) => [created, ...items.filter((item) => item.id !== created.id)]); } catch (e: any) { setError(e?.response?.data?.detail ?? e.message); } finally { setSubmitting(false); } };

  if (loading || products.loading) return <Spinner />;
  if (!questionnaire) return <ErrorBox message={error ?? t('business.assessment.loadFailed')} />;
  return <div><PageHeader title={t('business.assessment.title')} desc={t('business.assessment.desc')} />
    {error && <ErrorBox message={error} />}
    <section className="bg-white border rounded-xl p-5 mb-6"><div className="grid grid-cols-1 md:grid-cols-2 gap-4"><div><label className="block text-sm font-medium mb-2">{t('business.assessment.productLabel')}</label><select className={inputCls} value={productId} onChange={(e) => setProductId(e.target.value ? Number(e.target.value) : '')}><option value="">{t('business.assessment.selectProduct')}</option>{(products.data ?? []).map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}</select></div><div><label className="block text-sm font-medium mb-2">{t('business.assessment.presetLabel')}</label><select className={inputCls} value={preset} onChange={(e) => { const name = e.target.value; setPreset(name); if (name !== '自定义填写') setAnswers((a) => ({ ...a, ...questionnaire.presets[name] })); }}>{Object.keys(questionnaire.presets).map((name) => <option key={name}>{name}</option>)}</select></div></div></section>
    <section className="bg-indigo-50 border border-indigo-100 rounded-xl p-5 mb-6"><h2 className="font-semibold">{t('business.assessment.prefillTitle')}</h2><textarea className={`${inputCls} mt-3 bg-white`} rows={4} value={documentText} onChange={(e) => setDocumentText(e.target.value)} placeholder={t('business.assessment.prefillPlaceholder')}/><div className="mt-3 flex flex-wrap items-center gap-3"><button disabled={submitting || !documentText.trim()} onClick={prefill} className="px-4 py-2 bg-white border border-indigo-300 text-indigo-700 rounded-md text-sm disabled:opacity-50">{t('business.assessment.analyzePaste')}</button><label className="px-4 py-2 bg-white border border-indigo-300 text-indigo-700 rounded-md text-sm cursor-pointer">{t('business.assessment.uploadLabel')}<input type="file" accept=".txt,.md,.pdf,.docx" className="hidden" onChange={(e) => upload(e.target.files?.[0])}/></label></div>{note && <p className="text-sm text-indigo-700 mt-2">{note}</p>}</section>
    <div className="space-y-5">{grouped.map(({ module, questions }) => <section key={module} className="bg-white border rounded-xl p-5"><h2 className="font-semibold mb-4">{module}</h2><div className="space-y-5">{questions.map((q) => <div key={q.key}><label className="block text-sm text-slate-800 mb-2">{q.text}</label>{q.type === 'yesno' ? <div className="flex gap-4">{[{ label: t('business.assessment.yes'), value: true }, { label: t('business.assessment.no'), value: false }].map((o) => <label key={o.label} className="flex items-center gap-2 text-sm"><input type="radio" name={q.key} checked={answers[q.key] === o.value} onChange={() => update(q.key, o.value)}/>{o.label}</label>)}</div> : q.type === 'select' ? <select className={inputCls} value={(answers[q.key] as string) ?? ''} onChange={(e) => update(q.key, e.target.value)}>{q.options.map((o) => <option key={o}>{o}</option>)}</select> : <div className="flex flex-wrap gap-3">{q.options.map((o) => { const selected = (answers[q.key] as string[] ?? []).includes(o); return <label key={o} className="flex items-center gap-2 text-sm"><input type="checkbox" checked={selected} onChange={() => update(q.key, selected ? (answers[q.key] as string[]).filter((v) => v !== o) : [...((answers[q.key] as string[]) ?? []), o])}/>{o}</label>; })}</div>}</div>)}</div></section>)}</div>
    <button disabled={submitting || productId === ''} onClick={submit} className="mt-6 px-6 py-3 bg-indigo-600 text-white rounded-lg font-medium disabled:opacity-50">{submitting ? t('business.assessment.submitting') : t('business.assessment.submit')}</button>
    {result && <AssessmentResult result={result} />}
    {history.length > 0 && <section className="bg-white border rounded-xl p-5 mt-8"><h2 className="font-semibold mb-4">{t('business.assessment.historyTitle')}</h2><div className="flex items-end gap-2 h-32 border-b border-gray-200 pb-2">{[...history].reverse().slice(-12).map((item) => <button key={item.id} onClick={() => setResult(item)} className="flex-1 min-w-5 bg-indigo-400 hover:bg-indigo-600 rounded-t relative" style={{ height: `${Math.max(8, item.score)}%` }} title={t('business.assessment.historyTip', { id: item.id, score: item.score })}><span className="absolute -top-5 left-1/2 -translate-x-1/2 text-[10px] text-gray-500">{item.score}</span></button>)}</div><div className="mt-3 text-xs text-gray-500">{t('business.assessment.historyNote')}</div></section>}
  </div>;
}
