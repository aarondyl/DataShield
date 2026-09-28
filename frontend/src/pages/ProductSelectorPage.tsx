import { Link } from 'react-router-dom';

const products = [
  { index: '01', name: 'DataShield 企业版', eyebrow: '面向出海企业', copy: '持续监控法规变化，理解变化对企业产品与业务的影响，并转化为可执行的合规任务。', features: ['持续监管', '产品合规', '法规影响分析', '整改闭环'], to: '/business', cta: '进入企业版' },
  { index: '02', name: 'DataShield 开发者版', eyebrow: '面向开发者', copy: '快速检查应用、软件服务与网站的数据和隐私风险，在发布之前获得明确的修复路径。', features: ['合规自查', '隐私政策生成', '隐私政策检查', '整改建议'], to: '/developer', cta: '开始检查' },
];

export default function ProductSelectorPage() {
  return <div className="selector-page"><div className="ambient-grid" />
    <header className="selector-header"><div className="selector-brand"><span className="brand-mark">D</span><strong>DataShield</strong></div><span>法规 → 影响 → 行动</span></header>
    <main className="selector-main"><div className="selector-intro"><span className="eyebrow">智能监管与合规平台</span><h1>选择适合你的<br />DataShield 工作方式</h1><p>一套智能底座，两种专注的工作方式。</p></div>
      <div className="product-grid">{products.map((product) => <Link className="product-card" to={product.to} key={product.name}><div className="product-index">{product.index}</div><div className="product-body"><span className="eyebrow">{product.eyebrow}</span><h2>{product.name}</h2><p>{product.copy}</p><div className="feature-line">{product.features.map((feature) => <span key={feature}>{feature}</span>)}</div></div><div className="product-cta">{product.cta} <b>→</b></div></Link>)}</div>
    </main><footer className="selector-footer"><span>DATASHIELD / 2026</span><span>从法规到行动。</span></footer>
  </div>;
}
