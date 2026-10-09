import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { useCompanies, useProducts, useAnalysisRuns, useActions, useRegulations } from '../hooks';
import Spinner from '../components/Spinner';
import ErrorBox from '../components/ErrorBox';
import Reveal from '../components/Reveal';

function date(value: string | null | undefined) { if (!value) return '—'; const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleDateString('zh-CN').replace(/\//g, '.'); }

export default function DashboardPage() {
  const { t } = useTranslation();
  const riskLabels: Record<string, string> = { high: t('business.risk.high'), medium: t('business.risk.medium'), low: t('business.risk.low'), unknown: t('business.risk.unknown') };
  const statusLabels: Record<string, string> = { completed: t('business.status.completed'), degraded: t('business.status.degraded'), failed: t('business.status.failed') };
  const companies = useCompanies(); const products = useProducts(); const runs = useAnalysisRuns(); const actions = useActions(); const regulations = useRegulations();
  const all = [companies, products, runs, actions, regulations]; if (all.some((item) => item.loading)) return <Spinner />;
  const error = all.find((item) => item.error)?.error; if (error) return <ErrorBox message={error} />;
  const runList = runs.data ?? []; const latest = runList[0];
  const metrics: [string, string, number][] = [['01', t('business.dashboard.metricRegulations'), regulations.data?.length ?? 0], ['02', t('business.dashboard.metricHighRisk'), runList.filter((run) => run.risk_level === 'high').length], ['03', t('business.dashboard.metricActions'), actions.data?.length ?? 0], ['04', t('business.dashboard.metricPassports'), products.data?.length ?? 0]];
  return <div className="business-dashboard"><section className="hero business-hero"><div className="hero-grid" /><span className="eyebrow">{t('business.dashboard.eyebrow', { name: companies.data?.[0]?.name ?? t('business.dashboard.yourCompany') })}</span><h1>{t('business.dashboard.heroLine1')}<br /><em>{t('business.dashboard.heroLine2')}</em></h1><p>{t('business.dashboard.heroSub')}</p><Link className="primary-link" to="/business/impact">{t('business.dashboard.runAnalysis')} <span>→</span></Link></section>
    <Reveal className="metric-grid">{metrics.map(([number, label, value]) => <article key={number}><span>{number}</span><strong>{String(value).padStart(2, '0')}</strong><small>{label}</small></article>)}</Reveal>
    <Reveal className="latest-section"><div className="section-heading"><span className="eyebrow">{t('business.dashboard.latestEyebrow')}</span><Link to={latest ? `/report/${latest.id}` : '/business/impact'}>{t('business.dashboard.viewAnalysis')}</Link></div>{latest ? <div className="impact-feature"><div><span>{t('business.dashboard.analysisTarget')}</span><h2>{latest.product_name}</h2><p>{latest.company_name}</p></div><div><span>{t('business.dashboard.risk')}</span><strong className={latest.risk_level ?? 'unknown'}>{riskLabels[latest.risk_level ?? 'unknown']}</strong></div><div><span>{t('business.dashboard.status')}</span><h3>{statusLabels[latest.status] ?? latest.status}</h3><p>{date(latest.created_at)}</p></div></div> : <div className="empty-dark">{t('business.dashboard.emptyLatest')}</div>}</Reveal>
    <Reveal className="feed-section"><div className="section-heading"><span className="eyebrow">{t('business.dashboard.feedEyebrow')}</span><Link to="/business/regulations">{t('business.dashboard.openRegulations')}</Link></div><div className="timeline">{(regulations.data ?? []).slice(0, 4).map((item, index) => <article key={item.id}><div className="timeline-node" /><time>{date(item.published_at || item.effective_at)}</time><div><span>{index === 0 ? t('business.dashboard.latestUpdate') : t('business.dashboard.currentRegulation')}</span><h3>{item.name}</h3><p>{t('business.dashboard.jurisdictionArticles', { jurisdiction: item.jurisdiction, count: item.article_count })}</p></div></article>)}</div></Reveal>
  </div>;
}
