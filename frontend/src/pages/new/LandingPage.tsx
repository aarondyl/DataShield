import {useState} from 'react';
import {Link,useNavigate} from 'react-router-dom';
import {useTranslation} from 'react-i18next';
import {createDemoWorkspace} from '../../api/evaluation';
import {writeSession} from '../../features/auth/session';
import {writeSetup} from '../../features/onboarding/state';
import LanguageSwitcher from '../../components/LanguageSwitcher';
import BrandLogo from '../../components/BrandLogo';

const FEATURES:[string,string][]=[['selfAssessment','self-assessment'],['impactAnalysis','impact-analysis'],['regulationIntelligence','regulation-intelligence'],['remediationRoadmap','remediation-roadmap'],['privacyPolicyTools','privacy-policy-tools'],['documentPrefill','document-prefill']];
const FLOW=['describe','analyze','fix'];

export default function LandingPage(){
  const {t}=useTranslation();
  const nav=useNavigate();const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const demo=async()=>{setBusy(true);setError('');try{const d=await createDemoWorkspace();writeSession({name:'Aaron',email:'demo@datashield.local',edition:'developer',companyName:'Acme AI Labs',companyId:d.company_id});writeSetup({companyId:d.company_id,productId:d.product_id,productName:d.product_name,markets:['EU','US','UK'],method:'manual'});nav('/app/today')}catch(e:any){setError(e?.response?.data?.detail||t('appnew.landing.demoError'));setBusy(false)}};
  return <main className="ds-public ds-landing"><nav><Link to="/" className="ds-brand"><BrandLogo size={32}/><span>DataShield</span></Link><div className="ds-nav-links"><Link to="/features" className="ds-text-link">{t('appnew.landing.navFeatures')}</Link><Link to="/plans" className="ds-text-link">{t('appnew.landing.navPlans')}</Link><LanguageSwitcher/><Link to="/login" className="ds-text-link">{t('appnew.auth.logIn')}</Link><Link to="/choose" className="ds-button primary">{t('appnew.landing.navStart')}</Link></div></nav><section><BrandLogo size={72}/><span className="ds-eyebrow">{t('appnew.landing.eyebrow')}</span><h1>{t('appnew.landing.title')}</h1><p>{t('appnew.landing.subtitle')}</p><div className="ds-button-row"><Link className="ds-button primary" to="/choose">{t('appnew.landing.startDeveloper')} <span>→</span></Link><button className="ds-button quiet" disabled={busy} onClick={demo}>{busy?t('appnew.landing.preparingDemo'):t('appnew.landing.useDemo')}</button></div>{error&&<div className="ds-inline-error" role="alert">{error}</div>}</section><div className="ds-sec-head"><span className="ds-eyebrow">{t('appnew.landing.flowEyebrow')}</span><h2>{t('appnew.landing.flowTitle')}</h2><p>{t('appnew.landing.flowSubtitle')}</p></div><div className="ds-flow">{FLOW.map((k,i)=><article key={k}><b>{String(i+1).padStart(2,'0')}</b><h3>{t(`appnew.landing.flow.${k}.title`)}</h3><p>{t(`appnew.landing.flow.${k}.body`)}</p></article>)}</div><div className="ds-sec-head"><span className="ds-eyebrow">{t('appnew.landing.featuresEyebrow')}</span><h2>{t('appnew.landing.featuresTitle')}</h2><p>{t('appnew.landing.featuresSubtitle')}</p></div><div className="ds-feature-grid">{FEATURES.map(([k,anchor])=><Link key={k} to={`/features#${anchor}`}><span>{t(`appnew.landing.features.${k}.tag`)}</span><h3>{t(`appnew.landing.features.${k}.name`)}</h3><p>{t(`appnew.landing.features.${k}.desc`)}</p><strong>{t('appnew.landing.featureCta')}</strong></Link>)}</div><footer className="ds-landing-footer"><Link to="/" className="ds-brand"><BrandLogo size={28}/><span>{t('appnew.landing.brandFull')}</span></Link><p>{t('appnew.landing.footerDisclaimer')}</p></footer></main>
}
