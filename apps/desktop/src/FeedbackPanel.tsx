import { useEffect, useState } from 'react';
import type { Copy } from './i18n';
import { localApiRequest } from './local-api';
import type { Scope } from './remediation-api';

type Candidate = { id: number; status: 'PROPOSED' | 'NEEDS_CLARIFICATION' | 'CONFIRMED' | 'APPLIED' | 'REJECTED'; reasoning_summary: string; proposed_name?: string; proposed_status?: string; clarification_question?: string; applied_twin_version_id?: number; reanalysis_run_id?: number; last_error: string };
type Submission = { feedback: { id: number; raw_text: string; finding_id: number }; candidates: Candidate[] };
export function FeedbackPanel({ copy, workspace, findingId }: { copy: Copy; workspace: Scope; findingId: number }) {
  const c = copy.feedback;
  const [text, setText] = useState(''); const [answer, setAnswer] = useState('');
  const [items, setItems] = useState<Submission[]>([]); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const load = async () => { const rows = await localApiRequest<Submission[]>(`/api/v1/products/${workspace.productId}/feedback?tenant_id=${workspace.companyId}`); setItems(rows.filter(item => item.feedback.finding_id === findingId)); };
  useEffect(() => { void load().catch(() => setError(c.error)); }, [workspace, findingId]);
  const perform = async (action: () => Promise<unknown>) => { setBusy(true); setError(''); try { await action(); await load(); } catch { setError(c.error); await load().catch(() => {}); } finally { setBusy(false); } };
  const decide = (candidate: Candidate, action: 'confirm' | 'reject' | 'apply' | 'clarify') => perform(() => localApiRequest(`/api/v1/feedback-candidates/${candidate.id}/${action}`, 'POST', { tenant_id: workspace.companyId, ...(action === 'clarify' ? { answer } : { note: '' }) }));
  return <section className="empty-card"><h2>{c.title}</h2><p>{c.boundary}</p><p>{c.mock}</p>
    <form className="workspace-form" onSubmit={e => { e.preventDefault(); void perform(async () => { await localApiRequest('/api/v1/feedback', 'POST', { tenant_id: workspace.companyId, product_id: workspace.productId, finding_id: findingId, feedback_type: 'FACT_CORRECTION', raw_text: text, created_by: 'local-workspace-user' }); setText(''); }); }}><label>{c.input}<textarea required value={text} onChange={e => setText(e.target.value)} /></label><button className="primary" disabled={busy || !text.trim()}>{c.interpret}</button></form>
    {error && <p role="alert" className="form-error">{error}</p>}
    {items.map(item => <article key={item.feedback.id}><h3>{c.original}</h3><p>{item.feedback.raw_text}</p>{item.candidates.map(candidate => <div className="empty-card" key={candidate.id}><h3>{c.explanation}</h3><p>{candidate.reasoning_summary}</p><p>{candidate.proposed_name} · {candidate.proposed_status ? copy.twin.states[candidate.proposed_status as keyof typeof copy.twin.states] ?? candidate.proposed_status : ''}</p><p>{c.states[candidate.status]}</p>
      {candidate.status === 'NEEDS_CLARIFICATION' && <div className="workspace-form"><label>{candidate.clarification_question}<textarea value={answer} onChange={e => setAnswer(e.target.value)} /></label><button disabled={busy || !answer.trim()} onClick={() => void decide(candidate, 'clarify')}>{c.clarify}</button></div>}
      {candidate.status === 'PROPOSED' && <div className="buttons"><button className="primary" disabled={busy} onClick={() => void decide(candidate, 'confirm')}>{c.confirm}</button><button className="quiet" disabled={busy} onClick={() => void decide(candidate, 'reject')}>{c.reject}</button></div>}
      {candidate.status === 'CONFIRMED' && <><p>{c.confirmed}</p><button className="primary" disabled={busy} onClick={() => void decide(candidate, 'apply')}>{candidate.last_error ? c.retry : c.apply}</button></>}
      {candidate.applied_twin_version_id && <p>{c.version}: #{candidate.applied_twin_version_id}</p>}{candidate.reanalysis_run_id && <p>{c.run}: #{candidate.reanalysis_run_id}</p>}{candidate.last_error && <p role="alert">{c.failed}</p>}
      {candidate.status === 'APPLIED' && <p>{c.applied}</p>}
    </div>)}</article>)}
  </section>;
}
