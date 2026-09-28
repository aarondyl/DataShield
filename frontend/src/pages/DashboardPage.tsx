import { Link } from 'react-router-dom';
import { useCompanies, useProducts, useAnalysisRuns, useActions, useRegulations } from '../hooks';
import Spinner from '../components/Spinner';
import ErrorBox from '../components/ErrorBox';
import Reveal from '../components/Reveal';

function date(value: string | null | undefined) {
  if (!value) return '—';
  const parsed = new Date(value);
  return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleDateString('zh-CN').replace(/\//g, '.');
}

export default function DashboardPage() {
  const companies = useCompanies(); const products = useProducts(); const runs = useAnalysisRuns();
  const actions = useActions(); const regulations = useRegulations();
  const all = [companies, products, runs, actions, regulations];
  if (all.some((item) => item.loading)) return <Spinner />;
  const error = all.find((item) => item.error)?.error;
  if (error) return <ErrorBox message={error} />;
  const runList = runs.data ?? []; const actionList = actions.data ?? []; const latest = runList[0];
  const metrics: [string, string, number][] = [
    ['01', 'NEW REGULATORY UPDATES', regulations.data?.length ?? 0],
    ['02', 'HIGH RISK', runList.filter((run) => run.risk_level === 'high').length],
    ['03', 'PENDING ACTIONS', actionList.length],
    ['04', 'PRODUCT PASSPORTS', products.data?.length ?? 0],
  ];
  return <div className="business-dashboard">
    <section className="hero business-hero"><div className="hero-grid"/><span className="eyebrow">DATASHIELD BUSINESS / {companies.data?.[0]?.name ?? 'YOUR ORGANIZATION'}</span><h1>Regulatory intelligence,<br/><em>translated into action.</em></h1><p>What requires your attention today?</p><Link className="primary-link" to="/business/impact">RUN IMPACT ANALYSIS <span>→</span></Link></section>
    <Reveal className="metric-grid">{metrics.map(([number, label, value]) => <article key={number}><span>{number}</span><strong>{String(value).padStart(2, '0')}</strong><small>{label}</small></article>)}</Reveal>
    <Reveal className="latest-section"><div className="section-heading"><span className="eyebrow">LATEST IMPACT</span><Link to={latest ? `/report/${latest.id}` : '/business/impact'}>VIEW ANALYSIS →</Link></div>{latest ? <div className="impact-feature"><div><span>SUBJECT</span><h2>{latest.product_name}</h2><p>{latest.company_name}</p></div><div><span>RISK</span><strong className={latest.risk_level ?? 'unknown'}>{(latest.risk_level ?? 'UNKNOWN').toUpperCase()}</strong></div><div><span>STATUS</span><h3>{latest.status.toUpperCase()}</h3><p>{date(latest.created_at)}</p></div></div> : <div className="empty-dark">No analysis yet. Start with a product passport and run your first impact analysis.</div>}</Reveal>
    <Reveal className="feed-section"><div className="section-heading"><span className="eyebrow">REGULATORY FEED</span><Link to="/business/regulations">OPEN INTELLIGENCE →</Link></div><div className="timeline">{(regulations.data ?? []).slice(0, 4).map((item, index) => <article key={item.id}><div className="timeline-node"/><time>{date(item.published_at || item.effective_at)}</time><div><span>{index === 0 ? 'LATEST UPDATE' : 'ACTIVE REGULATION'}</span><h3>{item.name}</h3><p>{item.jurisdiction} · {item.article_count} verified articles</p></div></article>)}</div></Reveal>
  </div>;
}
