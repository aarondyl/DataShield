import { useEffect, useState } from 'react';
import type { Copy } from './i18n';
import { localApiRequest } from './local-api';
import type { Scope } from './remediation-api';
type Item = { id: string; type: string; title: string; summary: string; status: string; target: { finding_id?: number; remediation_id?: number } };
type Today = { needs_review: Item[]; waiting_for_you: Item[]; recently_completed: Item[]; latest_run: { id: number; status: string; model_provider: string } | null };
export function TodayPage({ copy, workspace, onNavigate }: { copy: Copy; workspace: Scope | null; onNavigate: (page: 'findings' | 'actions' | 'twin' | 'monitor', id?: number) => void }) {
  const c = copy.today;
  const [data, setData] = useState<Today | null>(null); const [sync, setSync] = useState<{ last_success_at: string; using_local_cache: boolean } | null>(null);
  const [events, setEvents] = useState<{ event: { event_id: string }; regulation: { name?: string } }[]>([]); const [error, setError] = useState(false);
  const load = async () => { if (!workspace) return; setError(false); try { const [next, state, changes] = await Promise.all([localApiRequest<Today>(`/api/v1/today?tenant_id=${workspace.companyId}&product_id=${workspace.productId}`), localApiRequest<typeof sync>('/api/v1/local-regulations/status'), localApiRequest<typeof events>('/api/v1/local-regulations/events?limit=5')]); setData(next); setSync(state); setEvents(changes); } catch { setError(true); } };
  useEffect(() => { void load(); }, [workspace]);
  const navigate = (item: Item) => onNavigate(item.type === 'REMEDIATION' ? 'actions' : item.target.finding_id ? 'findings' : 'twin', item.target.finding_id);
  const section = (title: string, items: Item[]) => <section className="empty-card"><h2>{title}</h2>{items.map(item => <article key={item.id}><button className="quiet" onClick={() => navigate(item)}>{item.type === 'MISSING_CONTEXT' ? c.context : item.type === 'FEEDBACK_CANDIDATE' ? c.feedback : item.title}</button><p>{item.summary}</p></article>)}</section>;
  return <section className="page business-page"><h1>{c.title}</h1>{!workspace ? <p>{c.setup}</p> : error ? <p role="alert">{c.error}<button onClick={() => void load()}>{copy.labels.retry}</button></p> : !data ? <p>{c.loading}</p> : <>
    {!sync?.last_success_at && <p>{c.noSync}<button onClick={() => onNavigate('monitor')}>{copy.monitor.title}</button></p>}{sync?.using_local_cache && <p>{copy.monitor.offline}</p>}
    {!data.latest_run ? <p>{c.noRun}</p> : <p>{c.lastRun}: #{data.latest_run.id} · {data.latest_run.status === 'FAILED' ? c.failed : data.latest_run.status === 'NEEDS_USER_INPUT' ? c.context : data.latest_run.status === 'COMPLETED' ? c.completed : c.running}{data.latest_run.model_provider === 'mock' && ` · ${c.mock}`}</p>}
    {data.needs_review.length > 0 && section(c.review, data.needs_review)}{data.waiting_for_you.length > 0 && section(c.waiting, data.waiting_for_you)}
    {data.latest_run?.status === 'COMPLETED' && sync?.last_success_at && !data.needs_review.length && !data.waiting_for_you.length && <p>{c.clear}</p>}
    {data.recently_completed.length > 0 && section(c.recent, data.recently_completed)}
    <section className="empty-card"><h2>{c.changes}</h2><p>{c.changeBoundary}</p>{events.length ? events.map(e => <p key={e.event.event_id}>{e.regulation.name || e.event.event_id}</p>) : <p>{copy.monitor.empty}</p>}</section>
  </>}</section>;
}
