import { useEffect, useMemo, useState } from 'react';
import type { Copy } from './i18n';
import { localApiRequest } from './local-api';
import { remediationApi, type Detail, type Finding, type Remediation, type Scope } from './remediation-api';

export function RemediationPage({ copy, workspace, initialFinding, onFinding }: { copy: Copy; workspace: Scope | null; initialFinding: number | null; onFinding: (id: number) => void }) {
  const c = copy.actions;
  const api = useMemo(() => workspace ? remediationApi(localApiRequest, workspace) : null, [workspace]);
  const [findings, setFindings] = useState<Finding[]>([]);
  const [rows, setRows] = useState<Remediation[]>([]);
  const [selected, setSelected] = useState(initialFinding ?? 0);
  const [detail, setDetail] = useState<Detail | null>(null);
  const [type, setType] = useState<Remediation['remediation_type']>('DOCUMENT_CHANGE');
  const [documentType, setDocumentType] = useState('');
  const [note, setNote] = useState('');
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [loaded, setLoaded] = useState(false);
  const refresh = async () => {
    if (!api) return;
    const fs = await api.findings();
    const groups = await Promise.all(fs.map(f => api.list(f.id)));
    setFindings(fs); setRows(groups.flat()); setLoaded(true);
  };
  useEffect(() => { let active = true; setBusy(true); setLoaded(false); void refresh().catch(() => { if (active) setError(c.error); }).finally(() => { if (active) setBusy(false); }); return () => { active = false; }; }, [api]);
  const perform = async (operation: () => Promise<Detail>) => {
    setBusy(true); setError('');
    try { setDetail(await operation()); await refresh(); } catch { setError(c.error); } finally { setBusy(false); }
  };
  if (!api) return <section className="page"><h1>{c.title}</h1><p>{c.setup}</p></section>;
  const r = detail?.remediation;
  return <section className="page business-page"><h1>{c.title}</h1><p>{c.boundary}</p>
    <form className="workspace-form" onSubmit={e => { e.preventDefault(); if (selected) void perform(() => api.create(selected, type, documentType.trim())); }}>
      <label>{c.finding}<select value={selected} onChange={e => setSelected(Number(e.target.value))}><option value={0}>{c.choose}</option>{findings.filter(f => f.status === 'OPEN').map(f => <option key={f.id} value={f.id}>{f.title}</option>)}</select></label>
      <label>{c.type}<select value={type} onChange={e => setType(e.target.value as Remediation['remediation_type'])}><option value="DOCUMENT_CHANGE">{c.document}</option><option value="CODE_CHANGE">{c.code}</option></select></label>
      {type === 'DOCUMENT_CHANGE' && <label>{c.documentType}<input required value={documentType} onChange={e => setDocumentType(e.target.value)} /></label>}
      <button className="primary" disabled={busy || !selected || (type === 'DOCUMENT_CHANGE' && !documentType.trim())}>{busy ? c.loading : c.create}</button>
    </form>
    {error && <p role="alert" className="form-error">{error}<button disabled={busy} onClick={() => { setBusy(true); void refresh().then(() => setError('')).catch(() => setError(c.error)).finally(() => setBusy(false)); }}>{copy.labels.retry}</button></p>}
    <div className="settings-list">{rows.map(row => <div key={row.id}><button className="quiet" disabled={busy} onClick={() => void perform(() => api.detail(row.id))}>{row.title}</button><span>{row.remediation_type === 'CODE_CHANGE' ? c.code : c.document} · {c.states[row.status]}</span></div>)}{loaded && !rows.length && <p>{c.empty}</p>}</div>
    {r && <article className="empty-card"><h2>{r.title}</h2><p>{r.summary}</p><p>{c.states[r.status]} · {r.remediation_type === 'CODE_CHANGE' ? c.code : c.document}</p>{r.model_provider === 'mock' && <p>{c.mock}</p>}<p>{c.boundary}</p>
      <h3>{c.content}</h3>{r.remediation_type === 'DOCUMENT_CHANGE' && <p>{c.draft}</p>}
      {(r.plan?.requested_changes ?? []).map((change, i) => <div key={i}><strong>{change.target}</strong><p>{change.change}</p><p>{change.rationale}</p></div>)}
      {(r.plan?.proposed_changes ?? []).map((change, i) => <div key={i}><strong>{change.section}</strong><p>{change.change}</p><p>{change.rationale}</p></div>)}
      <pre>{r.plan?.draft_text || r.plan?.coding_prompt}</pre><h3>{c.criteria}</h3><ul>{r.plan?.acceptance_criteria?.map((criterion, i) => <li key={i}>{criterion}</li>)}</ul>
      <h3>{c.requirements}</h3>{detail.requirements.map(req => <p key={req.id}>#{req.id} · {req.summary}</p>)}
      <h3>{c.evidence}</h3>{detail.legal_evidence.length ? detail.legal_evidence.map((e, i) => <div key={i}><strong>{e.regulation_name} · {e.article}</strong><p>{e.content}</p>{/^https?:\/\//.test(e.source_url) && <a href={e.source_url} target="_blank" rel="noreferrer">{c.source}</a>}</div>) : <p>{copy.findings.noEvidence}</p>}
      <p>{copy.findings.twin}: {detail.product_twin_version ? `v${detail.product_twin_version.version_number} (#${detail.product_twin_version.id})` : c.unavailable}</p>
      {r.status === 'PROPOSED' && <div className="workspace-form"><label>{c.note}<textarea value={note} onChange={e => setNote(e.target.value)} /></label><div className="buttons"><button className="primary" disabled={busy} onClick={() => void perform(() => api.decide(r.id, 'approve', note))}>{c.approve}</button><button className="quiet" disabled={busy} onClick={() => void perform(() => api.decide(r.id, 'reject', note))}>{c.reject}</button></div></div>}
      <button className="quiet" onClick={() => onFinding(r.finding_id)}>{c.back}</button>
    </article>}
  </section>;
}
