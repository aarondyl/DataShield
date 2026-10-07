import {useState} from 'react';
import {Link,useNavigate} from 'react-router-dom';
import {useTranslation} from 'react-i18next';
import {createDemoWorkspace} from '../../api/evaluation';
import {writeSession} from '../../features/auth/session';
import {writeSetup} from '../../features/onboarding/state';
import LanguageSwitcher from '../../components/LanguageSwitcher';

export default function LandingPage(){
  const {t}=useTranslation();
  const nav=useNavigate();const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const demo=async()=>{setBusy(true);setError('');try{const d=await createDemoWorkspace();writeSession({name:'Aaron',email:'demo@datashield.local',edition:'developer',companyName:'Acme AI Labs',companyId:d.company_id});writeSetup({companyId:d.company_id,productId:d.product_id,productName:d.product_name,markets:['EU','US','UK'],method:'manual'});nav('/app/today')}catch(e:any){setError(e?.response?.data?.detail||t('appnew.landing.demoError'));setBusy(false)}};
  return <main className="ds-public ds-landing"><nav><Link to="/" className="ds-brand"><span className="ds-logo">D</span><span>DataShield</span></Link><div style={{display:'flex',alignItems:'center',gap:18}}><LanguageSwitcher/><Link to="/login" className="ds-text-link">{t('appnew.landing.evaluationWorkspace')}</Link></div></nav><section><span className="ds-eyebrow">{t('appnew.landing.eyebrow')}</span><h1>{t('appnew.landing.title')}</h1><p>{t('appnew.landing.subtitle')}</p><div className="ds-button-row"><Link className="ds-button primary" to="/choose">{t('appnew.landing.startDeveloper')} <span>→</span></Link><button className="ds-button quiet" disabled={busy} onClick={demo}>{busy?t('appnew.landing.preparingDemo'):t('appnew.landing.useDemo')}</button></div>{error&&<div className="ds-inline-error" role="alert">{error}</div>}</section><div id="how" className="ds-how"><article><b>01</b><h2>{t('appnew.landing.how.understandTitle')}</h2><p>{t('appnew.landing.how.understandBody')}</p></article><article><b>02</b><h2>{t('appnew.landing.how.monitorTitle')}</h2><p>{t('appnew.landing.how.monitorBody')}</p></article><article><b>03</b><h2>{t('appnew.landing.how.remediateTitle')}</h2><p>{t('appnew.landing.how.remediateBody')}</p></article></div></main>
}
