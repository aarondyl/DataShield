import { Link } from 'react-router-dom';
import { useCompanies, useProducts, useAnalysisRuns, useActions, useRegulations } from '../hooks';
import Spinner from '../components/Spinner';
import ErrorBox from '../components/ErrorBox';
import Reveal from '../components/Reveal';

function date(value: string | null | undefined) { if (!value) return '—'; const parsed = new Date(value); return Number.isNaN(parsed.getTime()) ? '—' : parsed.toLocaleDateString('zh-CN').replace(/\//g, '.'); }
const riskLabels: Record<string, string> = { high: '高', medium: '中', low: '低', unknown: '未知' };
const statusLabels: Record<string, string> = { completed: '已完成', degraded: '降级完成', failed: '失败' };

export default function DashboardPage() {
  const companies = useCompanies(); const products = useProducts(); const runs = useAnalysisRuns(); const actions = useActions(); const regulations = useRegulations();
  const all = [companies, products, runs, actions, regulations]; if (all.some((item) => item.loading)) return <Spinner />;
  const error = all.find((item) => item.error)?.error; if (error) return <ErrorBox message={error} />;
  const runList = runs.data ?? []; const latest = runList[0];
  const metrics: [string, string, number][] = [['01', '法规更新', regulations.data?.length ?? 0], ['02', '高风险', runList.filter((run) => run.risk_level === 'high').length], ['03', '待办任务', actions.data?.length ?? 0], ['04', '产品护照', products.data?.length ?? 0]];
  return <div className="business-dashboard"><section className="hero business-hero"><div className="hero-grid" /><span className="eyebrow">DATASHIELD 企业版 / {companies.data?.[0]?.name ?? '你的企业'}</span><h1>监管情报，<br /><em>转化为行动。</em></h1><p>今天有哪些事项需要关注？</p><Link className="primary-link" to="/business/impact">运行影响分析 <span>→</span></Link></section>
    <Reveal className="metric-grid">{metrics.map(([number, label, value]) => <article key={number}><span>{number}</span><strong>{String(value).padStart(2, '0')}</strong><small>{label}</small></article>)}</Reveal>
    <Reveal className="latest-section"><div className="section-heading"><span className="eyebrow">最新影响分析</span><Link to={latest ? `/report/${latest.id}` : '/business/impact'}>查看分析 →</Link></div>{latest ? <div className="impact-feature"><div><span>分析对象</span><h2>{latest.product_name}</h2><p>{latest.company_name}</p></div><div><span>风险</span><strong className={latest.risk_level ?? 'unknown'}>{riskLabels[latest.risk_level ?? 'unknown']}</strong></div><div><span>状态</span><h3>{statusLabels[latest.status] ?? latest.status}</h3><p>{date(latest.created_at)}</p></div></div> : <div className="empty-dark">暂无分析记录。请先建立产品合规护照，再运行首次影响分析。</div>}</Reveal>
    <Reveal className="feed-section"><div className="section-heading"><span className="eyebrow">法规动态</span><Link to="/business/regulations">打开法规情报 →</Link></div><div className="timeline">{(regulations.data ?? []).slice(0, 4).map((item, index) => <article key={item.id}><div className="timeline-node" /><time>{date(item.published_at || item.effective_at)}</time><div><span>{index === 0 ? '最新更新' : '现行法规'}</span><h3>{item.name}</h3><p>{item.jurisdiction} · {item.article_count} 条已验证条款</p></div></article>)}</div></Reveal>
  </div>;
}
