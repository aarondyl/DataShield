import { useEffect, useState } from 'react';
import type { Copy } from './i18n';
import { localApiRequest } from './local-api';
import type { Scope } from './remediation-api';
type Fact = { id: number; group: string; name: string; status: string; confirmation_status: string };
type Twin = { version: number; facts: Fact[] };
export function TwinPage({ copy, workspace, onIntake }: { copy: Copy; workspace: Scope | null; onIntake: () => void }) {
  const c = copy.twin; const [twin, setTwin] = useState<Twin | null>(null); const [history, setHistory] = useState<{ version: number; created_at: string }[]>([]); const [error, setError] = useState(false); const [busy, setBusy] = useState(false);
  const base = workspace ? `/api/v1/ui/understanding/products/${workspace.productId}/twin` : '';
  const load = async () => { if (!workspace) return; setError(false); try { const [current, versions] = await Promise.all([localApiRequest<Twin>(`${base}?company_id=${workspace.companyId}`), localApiRequest<typeof history>(`${base}/versions?company_id=${workspace.companyId}`)]); setTwin(current); setHistory(versions); } catch { setError(true); } };
  useEffect(() => { void load(); }, [workspace]);
  const confirm = async (id: number) => { if (!workspace) return; setBusy(true); setError(false); try { await localApiRequest(`${base}/facts/${id}/confirm`, 'POST', { company_id: workspace.companyId, note: '', actor_label: 'local-workspace-user' }); await load(); } catch { setError(true); } finally { setBusy(false); } };
  return <section className="page business-page"><h1>{c.title}</h1><button className="primary" onClick={onIntake}>{copy.understanding.title}</button><p>{c.boundary}</p>{error && <p role="alert">{c.error}<button onClick={() => void load()}>{copy.labels.retry}</button></p>}
    {!workspace ? <p>{c.empty}</p> : !twin ? <p>{c.loading}</p> : <><h2>{c.version}: v{twin.version}</h2>{!twin.facts.length && <p>{c.empty}</p>}{twin.facts.map(f => <article className="empty-card" key={f.id}><strong>{f.name}</strong><p>{c.groups[f.group as keyof typeof c.groups] ?? f.group} · {c.states[f.status as keyof typeof c.states] ?? f.status} · {c.decisions[f.confirmation_status as keyof typeof c.decisions] ?? f.confirmation_status}</p>{f.confirmation_status === 'UNREVIEWED' && <button disabled={busy} onClick={() => void confirm(f.id)}>{c.confirm}</button>}</article>)}<h2>{c.history}</h2>{history.map(v => <p key={v.version}>v{v.version} · {apiDate(v.created_at).toLocaleString(document.documentElement.lang || 'zh-CN')}</p>)}</>}
  </section>;
}
import { apiDate } from './datetime';
