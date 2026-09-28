import { Link } from 'react-router-dom';
import Reveal from '../components/Reveal';

export default function DeveloperHomePage() {
  const steps = [['01', '告诉我们产品如何运行', '选择产品类型，并描述数据如何被收集和处理。'], ['02', '回答几个关键问题', '规则引擎检查高频风险，项目文档可以自动预填。'], ['03', '获得风险与行动建议', '得到风险、证据与 7 / 30 / 90 天整改建议。']];
  return <div className="immersive-page"><section className="hero developer-hero"><span className="eyebrow">DATASHIELD 开发者版 / 面向开发者</span><h1>专注构建。<br /><em>上线之前，</em><br />先检查合规。</h1><p>用一个清晰流程识别应用、软件服务和网站中的数据与隐私风险。</p><Link className="primary-link" to="/developer/check">开始检查 <span>→</span></Link></section>
    <Reveal className="process-section"><div className="section-rule" /><span className="eyebrow">使用流程</span><div className="process-grid">{steps.map(([number, title, description]) => <article key={number}><b>{number}</b><h3>{title}</h3><p>{description}</p></article>)}</div></Reveal>
  </div>;
}
