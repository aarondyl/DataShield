import {useState} from 'react';
import {Link,useNavigate,useSearchParams} from 'react-router-dom';
import {useTranslation} from 'react-i18next';
import {login,register} from '../../api/auth';
import {createDemoWorkspace} from '../../api/evaluation';
import {createCompany} from '../../api';
import {readEdition,writeSession,type Edition} from '../../features/auth/session';
import {writeSetup} from '../../features/onboarding/state';
import BrandLogo from '../../components/BrandLogo';

export default function AuthPage({mode}:{mode:'login'|'signup'}){
  const {t}=useTranslation();
  const friendlyError=(detail:unknown,fallback:string)=>{const d=String(detail||'');if(d==='Email already registered')return t('appnew.auth.emailTaken');if(d==='Invalid email or password')return t('appnew.auth.invalidCredentials');if(d==='Account disabled')return t('appnew.auth.accountDisabled');return d||fallback};
  const navigate=useNavigate();const [params]=useSearchParams();const edition=((params.get('edition') as Edition)||readEdition());
  const [name,setName]=useState('');const [email,setEmail]=useState('');const [password,setPassword]=useState('');const [confirm,setConfirm]=useState('');const [company,setCompany]=useState('');const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  if(window.datashieldDesktop)return <LocalWorkspace mode={mode} edition={edition}/>;
  const submit=async(e:React.FormEvent)=>{e.preventDefault();setError('');
    if(!email.trim()||!password||(mode==='signup'&&(!name.trim()||!confirm||!company.trim()))){setError(t('appnew.auth.requiredFields'));return}
    if(!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())){setError(t('appnew.auth.invalidEmail'));return}
    if(mode==='signup'&&password.length<8){setError(t('appnew.auth.passwordTooShort'));return}
    if(mode==='signup'&&password!==confirm){setError(t('appnew.auth.passwordMismatch'));return}
    setBusy(true);
    try{
      if(mode==='signup'){const user=await register({email,password,name,company_name:company,edition});writeSession({name,email:user.email,edition:user.edition,companyName:company,companyId:user.company_id});navigate('/onboarding/understand')}
      else{const user=await login({email,password});writeSession({name:user.email.split('@')[0],email:user.email,edition:user.edition,companyId:user.company_id});navigate('/app/today')}
    }catch(err:any){setError(friendlyError(err?.response?.data?.detail,mode==='signup'?t('appnew.auth.signupError'):t('appnew.auth.loginError')));setBusy(false)}};
  const demo=async()=>{setBusy(true);setError('');try{const d=await createDemoWorkspace();writeSession({name:'Aaron',email:'demo@datashield.local',edition:'developer',companyName:'Acme AI Labs',companyId:d.company_id});writeSetup({companyId:d.company_id,productId:d.product_id,productName:d.product_name,markets:['EU','US','UK'],method:'manual'});navigate('/app/today')}catch(err:any){setError(err?.response?.data?.detail||t('appnew.auth.demoError'));setBusy(false)}};
  return <main className="ds-auth"><div className="ds-auth-brand"><div><Link to="/" className="ds-brand"><BrandLogo size={34}/><span>DataShield</span></Link><p>{t('appnew.auth.brandTagline')}</p><ul className="ds-auth-points"><li>{t('appnew.auth.brandPoint1')}</li><li>{t('appnew.auth.brandPoint2')}</li><li>{t('appnew.auth.brandPoint3')}</li></ul></div><small className="ds-auth-legal">{t('appnew.auth.brandDisclaimer')}</small></div><form onSubmit={submit} noValidate><span className="ds-eyebrow">{t('appnew.auth.editionEyebrow',{edition:t(`appnew.auth.edition.${edition}`,{defaultValue:edition})})}</span><h1>{mode==='signup'?t('appnew.auth.createTitle'):t('appnew.auth.welcomeBack')}</h1>
    {mode==='signup'&&<label>{t('appnew.auth.name')}<input required value={name} onChange={e=>setName(e.target.value)} autoComplete="name"/></label>}
    <label>{edition==='enterprise'?t('appnew.auth.workEmail'):t('appnew.auth.email')}<input required type="email" value={email} onChange={e=>setEmail(e.target.value)} autoComplete="email"/></label>
    <label>{t('appnew.auth.password')}<input required type="password" value={password} onChange={e=>setPassword(e.target.value)} autoComplete={mode==='signup'?'new-password':'current-password'} minLength={mode==='signup'?8:undefined} maxLength={128}/></label>
    {mode==='signup'&&<label>{t('appnew.auth.confirmPassword')}<input required type="password" value={confirm} onChange={e=>setConfirm(e.target.value)} autoComplete="new-password" minLength={8} maxLength={128}/></label>}
    {mode==='signup'&&<label>{t('appnew.auth.workspaceName')}<input required value={company} onChange={e=>setCompany(e.target.value)} placeholder={edition==='enterprise'?t('appnew.auth.companyPlaceholder'):t('appnew.auth.workspacePlaceholder')}/></label>}
    {error&&<div className="ds-inline-error" role="alert">{error}</div>}
    <button className="ds-button primary" disabled={busy} type="submit">{busy?(mode==='signup'?t('appnew.auth.creatingAccount'):t('appnew.auth.signingIn')):(mode==='signup'?t('appnew.auth.createAccount'):t('appnew.auth.logIn'))} {!busy&&<span>→</span>}</button>
    <div className="ds-auth-note">{mode==='signup'?<>{t('appnew.auth.haveAccount')} <Link to="/login">{t('appnew.auth.logIn')}</Link></>:<>{t('appnew.auth.noAccount')} <Link to={`/signup?edition=${edition}`}>{t('appnew.auth.signUp')}</Link></>}</div>
    <div className="ds-auth-note"><button type="button" className="ds-button quiet" disabled={busy} onClick={demo}>{busy?t('appnew.auth.preparingDemo'):t('appnew.auth.tryDemo')}</button></div>
  </form></main>
}

function LocalWorkspace({mode,edition}:{mode:'login'|'signup';edition:Edition}){
  const {t}=useTranslation();const navigate=useNavigate();const [name,setName]=useState('');const [company,setCompany]=useState('');const [busy,setBusy]=useState(false);const [error,setError]=useState('');
  const create=async(e:React.FormEvent)=>{e.preventDefault();setBusy(true);setError('');try{const workspace=await createCompany({name:company,industry:'',country:'',target_markets:[],business_model:'offline'});writeSession({name,email:'',edition,companyName:company,companyId:workspace.id});navigate('/onboarding/understand')}catch(err:any){setError(err?.response?.data?.detail||err.message||t('appnew.auth.localMode.createError'));setBusy(false)}};
  return <main className="ds-auth"><div className="ds-auth-brand"><div><Link to="/" className="ds-brand"><BrandLogo size={34}/><span>DataShield</span></Link><p>{t('appnew.auth.localMode.tagline')}</p><ul className="ds-auth-points"><li>{t('appnew.auth.localMode.privacy')}</li><li>{t('appnew.auth.localMode.persistence')}</li><li>{t('appnew.auth.localMode.cloudStatus')}</li></ul></div><small className="ds-auth-legal">{t('appnew.auth.brandDisclaimer')}</small></div><form onSubmit={create}><span className="ds-eyebrow">{t('appnew.auth.localMode.eyebrow')}</span><h1>{mode==='signup'?t('appnew.auth.localMode.createTitle'):t('appnew.auth.localMode.loginTitle')}</h1><p>{mode==='signup'?t('appnew.auth.localMode.createBody'):t('appnew.auth.localMode.loginBody')}</p>{mode==='signup'&&<><label>{t('appnew.auth.name')}<input required value={name} onChange={e=>setName(e.target.value)} autoComplete="name"/></label><label>{t('appnew.auth.workspaceName')}<input required value={company} onChange={e=>setCompany(e.target.value)}/></label>{error&&<div className="ds-inline-error" role="alert">{error}</div>}<button className="ds-button primary" disabled={busy}>{busy?t('appnew.auth.localMode.creating'):t('appnew.auth.localMode.createButton')} <span>→</span></button></>}{mode==='login'&&<><div className="ds-inline-error" role="status">{t('appnew.auth.localMode.cloudUnavailable')}</div><Link className="ds-button primary" to={`/signup?edition=${edition}`}>{t('appnew.auth.localMode.offlineButton')} <span>→</span></Link></>}<div className="ds-auth-note"><Link to="/">{t('appnew.auth.localMode.back')}</Link></div></form></main>
}
