import {useEffect} from 'react';
import {Link,useLocation} from 'react-router-dom';
import {useTranslation} from 'react-i18next';
import LanguageSwitcher from '../../components/LanguageSwitcher';
import BrandLogo from '../../components/BrandLogo';

const SECTIONS:[string,string,string][]=[['selfAssessment','self-assessment','developer'],['impactAnalysis','impact-analysis','enterprise'],['regulationIntelligence','regulation-intelligence','enterprise'],['remediationRoadmap','remediation-roadmap','enterprise'],['privacyPolicyTools','privacy-policy-tools','developer'],['documentPrefill','document-prefill','developer']];

export default function FeaturesPage(){
  const {t}=useTranslation();const {hash}=useLocation();
  useEffect(()=>{if(hash){document.getElementById(hash.slice(1))?.scrollIntoView({behavior:'smooth'})}},[hash]);
  return <main className="ds-public ds-feature-page"><nav><Link to="/" className="ds-brand"><BrandLogo size={30}/><span>DataShield</span></Link><div style={{display:'flex',alignItems:'center',gap:18}}><Link to="/features" className="ds-text-link">{t('appnew.landing.navFeatures')}</Link><Link to="/plans" className="ds-text-link">{t('appnew.landing.navPlans')}</Link><LanguageSwitcher/><Link to="/login" className="ds-text-link">{t('appnew.landing.evaluationWorkspace')}</Link></div></nav><header className="ds-page-head"><span className="ds-eyebrow">{t('appnew.features.eyebrow')}</span><h1>{t('appnew.features.title')}</h1><p>{t('appnew.features.subtitle')}</p></header>{SECTIONS.map(([k,anchor,edition],i)=><article key={k} id={anchor} className="ds-feature-sec"><div><b className="ds-feature-idx">{String(i+1).padStart(2,'0')}</b><h2>{t(`appnew.features.items.${k}.name`)}</h2><div className="ds-fio"><h4>{t('appnew.features.whatLabel')}</h4><p>{t(`appnew.features.items.${k}.what`)}</p></div><div className="ds-fio"><h4>{t('appnew.features.howLabel')}</h4><p>{t(`appnew.features.items.${k}.how`)}</p></div><div className="ds-fio"><h4>{t('appnew.features.outputLabel')}</h4><p>{t(`appnew.features.items.${k}.output`)}</p></div><Link className={`ds-button ${edition==='developer'?'primary':'quiet'}`} to={`/signup?edition=${edition}`}>{t(edition==='developer'?'appnew.features.ctaDeveloper':'appnew.features.ctaEnterprise')}</Link></div><div className="ds-shot" aria-hidden="true">{t('appnew.features.screenshotPlaceholder')}</div></article>)}</main>
}
