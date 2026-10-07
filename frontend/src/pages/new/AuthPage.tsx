import {useState} from 'react';
import {Link,useNavigate,useSearchParams} from 'react-router-dom';
import {login,register} from '../../api/auth';
import {createDemoWorkspace} from '../../api/evaluation';
import {readEdition,writeSession,type Edition} from '../../features/auth/session';
import {writeSetup} from '../../features/onboarding/state';

export default function AuthPage({mode}:{mode:'login'|'signup'}){
  const navigate=useNavigate();const [params]=useSearchParams();const edition=((params.get('edition') as Edition)||readEdition());
  const [name,setName]=useState('');const [email,setEmail]=useState('');const [password,setPassword]=useState('');const [confirm,setConfirm]=useState('');const [company,setCompany]=useState('');const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const submit=async(e:React.FormEvent)=>{e.preventDefault();setError('');
    if(mode==='signup'&&password!==confirm){setError('Passwords do not match.');return}
    setBusy(true);
    try{
      if(mode==='signup'){const user=await register({email,password,name,company_name:company,edition});writeSession({name,email:user.email,edition:user.edition,companyName:company,companyId:user.company_id});navigate('/onboarding/understand')}
      else{const user=await login({email,password});writeSession({name:user.email.split('@')[0],email:user.email,edition:user.edition,companyId:user.company_id});navigate('/app/today')}
    }catch(err:any){setError(err?.response?.data?.detail||(mode==='signup'?'We could not create your account. Please try again.':'We could not sign you in. Please check your credentials and try again.'));setBusy(false)}};
  const demo=async()=>{setBusy(true);setError('');try{const d=await createDemoWorkspace();writeSession({name:'Aaron',email:'demo@datashield.local',edition:'developer',companyName:'Acme AI Labs',companyId:d.company_id});writeSetup({companyId:d.company_id,productId:d.product_id,productName:d.product_name,markets:['EU','US','UK'],method:'manual'});navigate('/app/today')}catch(err:any){setError(err?.response?.data?.detail||'The demo workspace could not be prepared. Please try again.');setBusy(false)}};
  return <main className="ds-auth"><div className="ds-auth-brand"><Link to="/" className="ds-brand"><span className="ds-logo">D</span><span>DataShield</span></Link><p>Continuous compliance for products that keep changing. Sign in to your workspace or create a new one.</p></div><form onSubmit={submit}><span className="ds-eyebrow">{edition} edition</span><h1>{mode==='signup'?'Create your DataShield account':'Welcome back'}</h1>
    {mode==='signup'&&<label>Name<input required value={name} onChange={e=>setName(e.target.value)} autoComplete="name"/></label>}
    <label>{edition==='enterprise'?'Work email':'Email'}<input required type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email"/></label>
    <label>Password<input required type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete={mode==='signup'?'new-password':'current-password'} minLength={mode==='signup'?8:undefined} maxLength={128}/></label>
    {mode==='signup'&&<label>Confirm password<input required type="password" value={confirm} onChange={e=>setConfirm(e.target.value)} autoComplete="new-password" minLength={8} maxLength={128}/></label>}
    {mode==='signup'&&<label>Workspace name<input required value={company} onChange={e=>setCompany(e.target.value)} placeholder={edition==='enterprise'?'Company name':'My product workspace'}/></label>}
    {error&&<div className="ds-inline-error" role="alert">{error}</div>}
    <button className="ds-button primary" disabled={busy} type="submit">{busy?(mode==='signup'?'Creating account…':'Signing in…'):(mode==='signup'?'Create account':'Log in')} {!busy&&<span>→</span>}</button>
    <div className="ds-auth-note">{mode==='signup'?<>Already have an account? <Link to="/login">Log in</Link></>:<>No account yet? <Link to={`/signup?edition=${edition}`}>Sign up</Link></>}</div>
    <div className="ds-auth-note"><button type="button" className="ds-button quiet" disabled={busy} onClick={demo}>{busy?'Preparing your demo…':'Try the demo first (no sign-up required)'}</button></div>
  </form></main>
}
