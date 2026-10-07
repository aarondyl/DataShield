import {useEffect,useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {fetchMe,logout,type MeResponse} from '../../api/auth';
import {signOutEvaluation} from '../../api/evaluation';
import {clearSession,readSession} from '../../features/auth/session';
import {clearSetup,readSetup} from '../../features/onboarding/state';

export default function SettingsPage(){const nav=useNavigate();const session=readSession();const setup=readSetup();const [busy,setBusy]=useState(false);const [me,setMe]=useState<MeResponse|null>(null);
  useEffect(()=>{fetchMe().then(setMe).catch(()=>{})},[]);
  const account=me&&'user_id' in me?me:null;
  const signout=async()=>{setBusy(true);try{await signOutEvaluation()}finally{clearSession();clearSetup();nav('/')}};
  const logoutAccount=async()=>{setBusy(true);try{await logout()}finally{clearSession();clearSetup();nav('/login')}};
  const restart=()=>{clearSetup();nav('/onboarding/understand')};return <div className="ds-page ds-settings"><header className="ds-page-header"><span className="ds-eyebrow">Settings</span><h1>Workspace</h1><p>Your isolated DataShield evaluation environment.</p></header><section className="ds-action-block"><h2>Account</h2><div><dl><dt>Email</dt><dd>{account?account.email:session?.email||'—'}</dd><dt>Edition</dt><dd>{account?account.edition:session?.edition||'developer'}</dd><dt>Email verification</dt><dd>{account?(account.email_verified?'Verified':'Not verified yet'):'No registered account on this session'}</dd></dl><button className="ds-button quiet" disabled={busy} onClick={logoutAccount}>{busy?'Signing out…':'Log out'}</button></div></section><section className="ds-action-block"><h2>Evaluation workspace</h2><div><dl><dt>Company</dt><dd>{session?.companyName||'Evaluation workspace'}</dd><dt>Edition</dt><dd>{session?.edition||'Developer'}</dd><dt>Current product</dt><dd>{setup?.productName||'Not set up yet'}</dd><dt>Session</dt><dd>{account?'Registered account session':'Evaluation session · Production authentication is not enabled'}</dd></dl></div></section><div className="ds-button-row"><button className="ds-button quiet" onClick={restart}>Restart onboarding</button><button className="ds-button primary" disabled={busy} onClick={signout}>{busy?'Signing out…':'Sign out evaluation session'}</button></div></div>}
