import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

export default function ProductSelectorPage() {
  const { t } = useTranslation();
  const products = [
    { index: '01', name: t('misc.productSelector.enterprise.name'), eyebrow: t('misc.productSelector.enterprise.eyebrow'), copy: t('misc.productSelector.enterprise.copy'), features: [t('misc.productSelector.enterprise.features.monitoring'), t('misc.productSelector.enterprise.features.product'), t('misc.productSelector.enterprise.features.impact'), t('misc.productSelector.enterprise.features.remediation')], to: '/business', cta: t('misc.productSelector.enterprise.cta') },
    { index: '02', name: t('misc.productSelector.developer.name'), eyebrow: t('misc.productSelector.developer.eyebrow'), copy: t('misc.productSelector.developer.copy'), features: [t('misc.productSelector.developer.features.selfCheck'), t('misc.productSelector.developer.features.policyGenerator'), t('misc.productSelector.developer.features.policyCheck'), t('misc.productSelector.developer.features.advice')], to: '/developer', cta: t('misc.productSelector.developer.cta') },
  ];
  return <div className="selector-page"><div className="ambient-grid" />
    <header className="selector-header"><div className="selector-brand"><span className="brand-mark">D</span><strong>DataShield</strong></div><span>{t('misc.productSelector.tagline')}</span></header>
    <main className="selector-main"><div className="selector-intro"><span className="eyebrow">{t('misc.productSelector.introEyebrow')}</span><h1>{t('misc.productSelector.introTitle1')}<br />{t('misc.productSelector.introTitle2')}</h1><p>{t('misc.productSelector.introDesc')}</p></div>
      <div className="product-grid">{products.map((product) => <Link className="product-card" to={product.to} key={product.name}><div className="product-index">{product.index}</div><div className="product-body"><span className="eyebrow">{product.eyebrow}</span><h2>{product.name}</h2><p>{product.copy}</p><div className="feature-line">{product.features.map((feature) => <span key={feature}>{feature}</span>)}</div></div><div className="product-cta">{product.cta} <b>→</b></div></Link>)}</div>
    </main><footer className="selector-footer"><span>DATASHIELD / 2026</span><span>{t('misc.productSelector.footerSlogan')}</span></footer>
  </div>;
}
