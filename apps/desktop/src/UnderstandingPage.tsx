import { useEffect, useRef, useState } from 'react';
import type { Copy } from './i18n';
import { localApiRequest, selectRepository } from './local-api';
import type { Scope } from './remediation-api';
type Result = { features: { name: string; status: string }[]; evidence: { evidence_id: string; type: string; reason: string; file?: string; url?: string }[]; limitations: string[]; files_scanned?: number };
type Job = { analysis_id: string; kind: 'website' | 'repository'; status: 'PENDING' | 'RUNNING' | 'COMPLETED' | 'FAILED'; website_analysis?: Result; repository_analysis?: Result };
export function UnderstandingPage({ copy, workspace, onDone }: { copy: Copy; workspace: Scope; onDone: () => void }) {
  const c = copy.understanding;
  const [url, setUrl] = useState(''); const [repository, setRepository] = useState(''); const [description, setDescription] = useState('');
  const [job, setJob] = useState<Job | null>(null); const [busy, setBusy] = useState(false); const [error, setError] = useState('');
  const active = useRef(true);
  useEffect(() => { active.current = true; return () => { active.current = false; }; }, []);
  useEffect(() => {
    if (!job || error || !['PENDING', 'RUNNING'].includes(job.status)) return;
    const timer = window.setTimeout(() => { void localApiRequest<Job>(`/api/v1/ui/understanding/analysis/${job.kind}/${job.analysis_id}?company_id=${workspace.companyId}&product_id=${workspace.productId}`).then(next => { if (active.current) setJob(next); }).catch(() => setError(c.error)); }, 1000);
    return () => window.clearTimeout(timer);
  }, [job, workspace, error]);
  const analyze = async (kind: Job['kind']) => {
    setBusy(true); setError(''); setJob(null);
    try { const next = await localApiRequest<Job>(`/api/v1/ui/understanding/${kind}`, 'POST', { company_id: workspace.companyId, product_id: workspace.productId, product_description: description, ...(kind === 'website' ? { url } : { repository_path: repository, analysis_mode: 'FULL' }) }); if (active.current) setJob(next); } catch { setError(c.error); } finally { setBusy(false); }
  };
  const attach = async () => { if (!job) return; setBusy(true); setError(''); try { await localApiRequest(`/api/v1/ui/understanding/products/${workspace.productId}/twin/analyses`, 'POST', { company_id: workspace.companyId, analysis_id: job.analysis_id, kind: job.kind }); onDone(); } catch { setError(c.error); } finally { setBusy(false); } };
  const result = job?.website_analysis ?? job?.repository_analysis;
  const pending = busy || job?.status === 'PENDING' || job?.status === 'RUNNING';
  return <section className="empty-card"><h2>{c.title}</h2><p>{c.privacy}</p><div className="workspace-form"><label>{c.description}<textarea value={description} onChange={e => setDescription(e.target.value)} /></label><label>{c.url}<input type="url" value={url} onChange={e => setUrl(e.target.value)} /></label><button className="primary" disabled={pending || !url.trim()} onClick={() => void analyze('website')}>{c.website}</button><button className="quiet" disabled={pending} onClick={() => { setError(''); void selectRepository().then(path => { if (path) setRepository(path); }).catch(() => setError(c.selectionError)); }}>{c.select}</button>{repository && <p>{repository}</p>}<button className="primary" disabled={pending || !repository} onClick={() => void analyze('repository')}>{c.repository}</button></div>
    {pending && !error && <p>{c.pending}</p>}{job?.status === 'FAILED' && <p role="alert">{c.failed}</p>}{error && <p role="alert">{error}<button className="quiet" onClick={() => { setError(''); if (job?.status === 'FAILED') setJob(null); }}>{c.retry}</button></p>}
    {job?.status === 'COMPLETED' && result && <><h3>{c.features}</h3>{result.features.map((f, i) => <p key={i}>{f.name} · {f.status}</p>)}<h3>{c.evidence}</h3>{result.evidence.map(e => <p key={e.evidence_id}>{e.type} · {e.file || e.url} · {e.reason}</p>)}<p>{c.review}</p><button className="primary" disabled={busy} onClick={() => void attach()}>{c.attach}</button></>}
  </section>;
}
