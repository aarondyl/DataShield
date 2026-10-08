import type { Copy } from './i18n';
import { apiDate } from './datetime';

type LegalEvidence = { legal_unit_id: number; regulation_id: number; regulation_name: string; version_id: number; version: number; article: string; heading: string; content: string; source_url: string; requirement_ids: number[] };
export type FindingDetailData = {
  finding: { id: number; status: string; impact_level: string; title: string; applicability_summary: string; gap_summary: string; product_twin_version_id?: number; created_at: string };
  requirements: { id: number; summary: string; regulation_name: string; regulation_id: number; version_id: number; regulation_version?: number; legal_unit_id?: number; source_url: string }[];
  legal_evidence: LegalEvidence[];
  evidence_snapshots: { id: number; requirement_id?: number; snapshot: LegalEvidence }[];
  agent_run: { id: number; created_at: string; status: string; model_provider: string };
  product_twin_version?: { id: number; version_number?: number } | null;
};
export function FindingDetail({ copy, detail }: { copy: Copy; detail: FindingDetailData }) {
  const c = copy.findings;
  const locale = document.documentElement.lang || 'zh-CN';
  const time = apiDate(detail.finding.created_at);
  const evidence = detail.evidence_snapshots?.length ? detail.evidence_snapshots.map(e => ({ ...e.snapshot, key: `snapshot-${e.id}` })) : detail.legal_evidence.map((e, i) => ({ ...e, key: `legal-${i}` }));
  const source = (url: string) => /^https?:\/\//.test(url) ? <a href={url} target="_blank" rel="noreferrer">{c.officialSource}</a> : <span>{c.noEvidence}</span>;
  return <article className="empty-card"><h2>{detail.finding.title}</h2><p>{c.risk}: {c.risks[detail.finding.impact_level as keyof typeof c.risks] ?? detail.finding.impact_level} · {c.states[detail.finding.status as keyof typeof c.states] ?? detail.finding.status}</p>
    <p>{c.analysisTime}: {Number.isNaN(time.valueOf()) ? c.unavailable : new Intl.DateTimeFormat(locale, { dateStyle: 'medium', timeStyle: 'short' }).format(time)}</p>
    <p>{c.runRef}: #{detail.agent_run.id}</p>{detail.agent_run.model_provider === 'mock' && <p role="note">{c.mock}</p>}
    <p>{c.twin}: {detail.product_twin_version ? `v${detail.product_twin_version.version_number ?? '—'} (#${detail.product_twin_version.id})` : c.unavailable}</p>
    <h3>{c.applicability}</h3><p>{detail.finding.applicability_summary || c.unavailable}</p><h3>{c.gap}</h3><p>{detail.finding.gap_summary || c.unavailable}</p>
    <p>{c.sourceBoundary}</p>
    <h3>{c.requirements}</h3>{detail.requirements.length ? detail.requirements.map(r => <section key={r.id}><h4>#{r.id} · {r.regulation_name}</h4><p>{r.summary}</p><p>{c.regulationVersion}: {r.regulation_version ?? '—'} (#{r.version_id}) · {c.legalUnit}: #{r.legal_unit_id ?? '—'}</p>{source(r.source_url)}</section>) : <p>{c.noEvidence}</p>}
    <h3>{c.evidence}</h3>{evidence.length ? evidence.map(e => <section key={e.key}><h4>{e.regulation_name} · {e.article} · {e.heading}</h4><p>{c.regulationVersion}: {e.version} (#{e.version_id}) · {c.legalUnit}: #{e.legal_unit_id}</p><p>{c.requirements}: {(e.requirement_ids ?? []).map(id => `#${id}`).join(', ')}</p><p>{e.content}</p>{source(e.source_url)}</section>) : <p>{c.noEvidence}</p>}
  </article>;
}
