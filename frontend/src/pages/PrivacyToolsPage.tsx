import { useState } from 'react';
import { checkPolicy, generatePolicy, listAssessments } from '../api';
import type { Assessment, PolicyCheckResult } from '../types';
import PageHeader from '../components/PageHeader';
import ErrorBox from '../components/ErrorBox';

const inputCls = 'w-full border border-gray-300 rounded-md px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-indigo-500';

export default function PrivacyToolsPage({ mode = 'both' }: { mode?: 'generate' | 'check' | 'both' }) {
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [productName, setProductName] = useState('');
  const [companyName, setCompanyName] = useState('');
  const [contact, setContact] = useState('');
  const [generated, setGenerated] = useState('');
  const [policyText, setPolicyText] = useState('');
  const [checked, setChecked] = useState<PolicyCheckResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const loadLatest = async () => { setBusy(true); setError(null); try { const items = await listAssessments(); if (!items.length) throw new Error('请先完成一次合规自查'); setAssessment(items[0]); } catch (e: any) { setError(e.message); } finally { setBusy(false); } };
  const create = async () => { if (!assessment) return; setBusy(true); setError(null); try { const result = await generatePolicy({ answers: assessment.answers, product_name: productName || '【产品名称】', company_name: companyName || '【公司名称】', contact: contact || '【联系邮箱】' }); setGenerated(result.text); } catch (e: any) { setError(e?.response?.data?.detail ?? e.message); } finally { setBusy(false); } };
  const inspect = async () => { if (!policyText.trim()) return; setBusy(true); setError(null); try { setChecked(await checkPolicy(policyText)); } catch (e: any) { setError(e?.response?.data?.detail ?? e.message); } finally { setBusy(false); } };
  return <div><PageHeader title={mode === 'check' ? 'Privacy Policy Check' : mode === 'generate' ? 'Privacy Policy Generator' : '隐私政策工具'} desc={mode === 'check' ? '检查现有隐私政策是否覆盖关键法定要素。' : '根据最近一次合规评估生成可编辑的政策初稿。'} />{error && <ErrorBox message={error} />}
    <div className={`grid grid-cols-1 ${mode === 'both' ? 'xl:grid-cols-2' : ''} gap-6`}>
      {mode !== 'check' && <section className="bg-white border rounded-xl p-5"><div className="flex justify-between"><h2 className="font-semibold">隐私政策生成</h2><button onClick={loadLatest} className="text-sm text-indigo-600">载入最近评估</button></div><p className="text-xs text-gray-500 mt-1">{assessment ? `已载入评估 #${assessment.id}（${assessment.score}分）` : '需要先载入一份合规评估'}</p><div className="grid grid-cols-1 md:grid-cols-3 gap-3 mt-4"><input className={inputCls} placeholder="产品名称" value={productName} onChange={(e) => setProductName(e.target.value)}/><input className={inputCls} placeholder="公司名称" value={companyName} onChange={(e) => setCompanyName(e.target.value)}/><input className={inputCls} placeholder="联系邮箱" value={contact} onChange={(e) => setContact(e.target.value)}/></div><button disabled={!assessment || busy} onClick={create} className="mt-4 px-4 py-2 bg-indigo-600 text-white rounded-md text-sm disabled:opacity-50">生成政策初稿</button>{generated && <textarea className={`${inputCls} mt-4 font-mono`} rows={22} value={generated} onChange={(e) => setGenerated(e.target.value)}/>}</section>}
      {mode !== 'generate' && <section className="bg-white border rounded-xl p-5"><h2 className="font-semibold">隐私政策体检</h2><textarea className={`${inputCls} mt-4`} rows={12} value={policyText} onChange={(e) => setPolicyText(e.target.value)} placeholder="粘贴现有隐私政策全文…"/><button disabled={!policyText.trim() || busy} onClick={inspect} className="mt-3 px-4 py-2 bg-slate-900 text-white rounded-md text-sm disabled:opacity-50">检查法定要素</button>{checked && <div className="mt-5"><div className="text-3xl font-semibold">{checked.coverage}%</div><div className="text-sm text-gray-500">已覆盖 {checked.covered}/{checked.total} 项</div><div className="mt-4 space-y-2">{checked.items.map((item) => <div key={item.name} className={`p-3 rounded-lg border text-sm ${item.covered ? 'bg-emerald-50 border-emerald-200' : 'bg-red-50 border-red-200'}`}><b>{item.covered ? '✓' : '缺失'} {item.name}</b><div className="text-xs mt-1 opacity-75">{item.hint}</div></div>)}</div></div>}</section>}
    </div>
  </div>;
}
