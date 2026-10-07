import {useState} from 'react';
import {Link,useNavigate} from 'react-router-dom';
import {createDemoWorkspace} from '../../api/evaluation';
import {writeSession} from '../../features/auth/session';
import {writeSetup} from '../../features/onboarding/state';

export default function LandingPage(){
  const nav=useNavigate();const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const demo=async()=>{setBusy(true);setError('');try{const d=await createDemoWorkspace();writeSession({name:'Aaron',email:'demo@datashield.local',edition:'developer',companyName:'Acme AI Labs',companyId:d.company_id});writeSetup({companyId:d.company_id,productId:d.product_id,productName:d.product_name,markets:['EU','US','UK'],method:'manual'});nav('/app/today')}catch(e:any){setError(e?.response?.data?.detail||'The demo workspace could not be prepared. Please try again.');setBusy(false)}};
  return <main className="ds-public ds-landing"><nav><Link to="/" className="ds-brand"><span className="ds-logo">D</span><span>DataShield</span></Link><Link to="/login" className="ds-text-link">Evaluation workspace</Link></nav><section><span className="ds-eyebrow">Continuous compliance</span><h1>Continuous compliance for products that keep changing.</h1><p>DataShield understands your product, monitors regulatory change, finds what matters, and tells you exactly what to do next.</p><div className="ds-button-row"><Link className="ds-button primary" to="/choose">Start with Developer <span>→</span></Link><button className="ds-button quiet" disabled={busy} onClick={demo}>{busy?'Preparing your demo…':'Use demo workspace'}</button></div>{error&&<div className="ds-inline-error" role="alert">{error}</div>}</section><div id="how" className="ds-how"><article><b>01</b><h2>Understand</h2><p>Build an evidence-backed model of your product.</p></article><article><b>02</b><h2>Monitor</h2><p>Connect regulatory change to your actual context.</p></article><article><b>03</b><h2>Remediate</h2><p>Review grounded recommendations and verify corrections.</p></article></div></main>
}
