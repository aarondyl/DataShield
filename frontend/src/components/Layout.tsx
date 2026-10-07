import { useEffect, useState } from 'react';
import { Link, NavLink, Outlet, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { listCompanies } from '../api';
import BrandLogo from './BrandLogo';
type Mode = 'business' | 'developer';

export default function Layout({ mode }: { mode: Mode }) {
  const { t } = useTranslation();
  const location = useLocation();
  const [legacyState, setLegacyState] = useState<'probing' | 'enabled' | 'disabled'>('probing');
  useEffect(() => {
    let alive = true;
    listCompanies()
      .then(() => { if (alive) setLegacyState('enabled'); })
      .catch((e) => { if (alive) setLegacyState(e?.response?.data?.detail === 'Legacy tenant API is disabled' ? 'disabled' : 'enabled'); });
    return () => { alive = false; };
  }, []);
  const businessNav = [{ section: t('business.layout.nav.secOverview'), items: [{ to: '/business', label: t('business.layout.nav.today') }] }, { section: t('business.layout.nav.secCompany'), items: [{ to: '/business/company', label: t('business.layout.nav.company') }, { to: '/business/products', label: t('business.layout.nav.products') }] }, { section: t('business.layout.nav.secCompliance'), items: [{ to: '/business/risks', label: t('business.layout.nav.risks') }, { to: '/business/check', label: t('business.layout.nav.check') }, { to: '/business/impact', label: t('business.layout.nav.impact') }] }, { section: t('business.layout.nav.secRemediation'), items: [{ to: '/business/actions', label: t('business.layout.nav.actions') }] }, { section: t('business.layout.nav.secRegulations'), items: [{ to: '/business/regulations', label: t('business.layout.nav.regulationCenter') }] }];
  const developerNav = [{ section: t('business.layout.devNav.secHome'), items: [{ to: '/developer', label: t('business.layout.devNav.home') }] }, { section: t('business.layout.devNav.secProduct'), items: [{ to: '/developer/product', label: t('business.layout.devNav.productProfile') }] }, { section: t('business.layout.devNav.secCheck'), items: [{ to: '/developer/check', label: t('business.layout.devNav.quickCheck') }, { to: '/developer/sdk-scan', label: t('business.layout.devNav.sdkScan') }, { to: '/developer/policy-check', label: t('business.layout.devNav.policyCheck') }] }, { section: t('business.layout.devNav.secFix'), items: [{ to: '/developer/policy-generator', label: t('business.layout.devNav.policyGenerator') }, { to: '/developer/issues', label: t('business.layout.devNav.issues') }] }, { section: t('business.layout.devNav.secShip'), items: [{ to: '/developer/ready', label: t('business.layout.devNav.readyToShip') }] }, { section: t('business.layout.devNav.secReference'), items: [{ to: '/developer/regulations', label: t('business.layout.devNav.regulations') }] }];
  const nav = mode === 'business' ? businessNav : developerNav;
  return <div className={`app-shell mode-${mode}`}><aside className="app-sidebar"><NavLink to="/" className="brand-lockup"><BrandLogo size={34}/><span><strong>DataShield</strong><small>{t('business.layout.tagline')}</small></span></NavLink><div className="mode-label"><span>{mode === 'business' ? t('business.layout.modeBusiness') : t('business.layout.modeDeveloper')}</span><i /></div><nav className="nav-groups">{nav.map((group) => <div className="nav-group" key={group.section}><div className="nav-section">{group.section}</div>{group.items.map((item) => <NavLink key={item.to} to={item.to} end={item.to === `/${mode}`} className={({ isActive }) => isActive ? 'nav-link active' : 'nav-link'}>{item.label}<span>→</span></NavLink>)}</div>)}</nav><div className="sidebar-foot"><div><strong>{mode === 'business' ? t('business.layout.footerBusinessName') : t('business.layout.footerDeveloperName')}</strong><small>{mode === 'business' ? t('business.layout.footerBusinessDesc') : t('business.layout.footerDeveloperDesc')}</small></div><NavLink to="/">{t('business.layout.switchProduct')}</NavLink></div></aside><main className="app-main" key={location.pathname}>{legacyState === 'disabled' ? <section className="legacy-disabled"><span className="eyebrow">{t('business.legacyDisabled.eyebrow')}</span><h1>{t('business.legacyDisabled.title')}</h1><p>{t('business.legacyDisabled.body')}</p><div className="legacy-disabled-actions"><Link className="primary-link" to="/choose">{t('business.legacyDisabled.cta')} <span>→</span></Link><Link className="primary-link secondary" to="/">{t('business.legacyDisabled.back')}</Link></div></section> : legacyState === 'enabled' ? <Outlet /> : null}</main></div>;
}
