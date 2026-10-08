import { useEffect, useState } from 'react';
import { localApiRequest } from './local-api';
import type { Copy } from './i18n';
import { apiDate } from './datetime';
type SyncState = { scope: string; using_local_cache: boolean; last_success_at: string; last_error: string };
type Event = { event: { event_id: string; payload?: { materiality?: string; topics?: string[] } }; regulation: { name?: string; jurisdiction?: string; source_url?: string } };
export function MonitorPage({ copy }: { copy: Copy }) {
  const c = copy.monitor; const [state, setState] = useState<SyncState | null>(null); const [events, setEvents] = useState<Event[]>([]); const [busy, setBusy] = useState(false); const [error, setError] = useState(false);
  const load = async () => { const [s, e] = await Promise.all([localApiRequest<SyncState>('/api/v1/local-regulations/status'), localApiRequest<Event[]>('/api/v1/local-regulations/events')]); setState(s); setEvents(e); };
  useEffect(() => { void load().catch(() => setError(true)); }, []);
  const sync = async () => { setBusy(true); setError(false); try { await localApiRequest('/api/v1/local-regulations/sync', 'POST'); } catch { setError(true); } finally { try { await load(); } catch { setError(true); } setBusy(false); } };
  return <section className="page business-page"><h1>{c.title}</h1><p>{c.body}</p><p>{copy.findings.sourceBoundary}</p>{state?.using_local_cache && <p role="status">{c.offline}</p>}{error && <p role="alert">{c.error}</p>}
    <div className="settings-list"><div><strong>{c.lastSync}</strong><span>{state?.last_success_at ? apiDate(state.last_success_at).toLocaleString(document.documentElement.lang || 'zh-CN') : c.never}</span></div><div><strong>{c.scope}</strong><span>{state ? (state.scope === 'all:jurisdiction=*' ? c.all : state.scope) : c.loading}</span></div><div><strong>{c.status}</strong><span>{!state ? c.loading : state.using_local_cache ? c.offline : state.last_success_at ? c.success : c.never}</span></div></div>
    <button className="primary" disabled={busy} onClick={() => void sync()}>{busy ? c.syncing : c.sync}</button>
    <div className="settings-list">{events.length ? events.map(e => <article key={e.event.event_id}><h3>{e.regulation.name || e.event.event_id}</h3><p>{e.regulation.jurisdiction || '—'} · {copy.findings.risks[(e.event.payload?.materiality || '') as keyof typeof copy.findings.risks] ?? c.unknown} · {(e.event.payload?.topics || []).join(', ')}</p>{e.regulation.source_url && /^https:\/\//.test(e.regulation.source_url) ? <a href={e.regulation.source_url} target="_blank" rel="noreferrer">{copy.findings.officialSource}</a> : <p>{copy.findings.noEvidence}</p>}</article>) : <p>{c.empty}</p>}</div>
  </section>;
}
