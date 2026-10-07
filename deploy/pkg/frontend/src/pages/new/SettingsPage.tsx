import {useEffect,useState} from 'react';
import {useNavigate} from 'react-router-dom';
import {useTranslation} from 'react-i18next';
import {fetchMe,logout,type MeResponse} from '../../api/auth';
import {signOutEvaluation} from '../../api/evaluation';
import {clearSession,readSession} from '../../features/auth/session';
import {clearSetup,readSetup} from '../../features/onboarding/state';

export default function SettingsPage(){const {t}=useTranslation();const nav=useNavigate();const session=readSession();const setup=readSetup();const [busy,setBusy]=useState(false);const [me,setMe]=useState<MeResponse|null>(null);
  useEffect(()=>{fetchMe().then(setMe).catch(()=>{})},[]);
  const account=me&&'user_id' in me?me:null;
  const editionLabel=(e?:string)=>t(`appnew.settings.editions.${(e||'developer').toLowerCase()}`,{defaultValue:e||'developer'});
  const signout=async()=>{setBusy(true);try{await signOutEvaluation()}finally{clearSession();clearSetup();nav('/')}};
  const logoutAccount=async()=>{setBusy(true);try{await logout()}finally{clearSession();clearSetup();nav('/login')}};
  const restart=()=>{clearSetup();nav('/onboarding/understand')};return <div className="ds-page ds-settings"><header className="ds-page-header"><span className="ds-eyebrow">{t('appnew.settings.eyebrow')}</span><h1>{t('appnew.settings.title')}</h1><p>{t('appnew.settings.subtitle')}</p></header><section className="ds-action-block"><h2>{t('appnew.settings.account')}</h2><div><dl><dt>{t('appnew.settings.email')}</dt><dd>{account?account.email:session?.email||'—'}</dd><dt>{t('appnew.settings.edition')}</dt><dd>{editionLabel(account?account.edition:session?.edition)}</dd><dt>{t('appnew.settings.emailVerification')}</dt><dd>{account?(account.email_verified?t('appnew.settings.verified'):t('appnew.settings.notVerified')):t('appnew.settings.noAccount')}</dd></dl><button className="ds-button quiet" disabled={busy} onClick={logoutAccount}>{busy?t('appnew.settings.signingOut'):t('appnew.settings.logOut')}</button></div></section><section className="ds-action-block"><h2>{t('appnew.settings.evaluationWorkspace')}</h2><div><dl><dt>{t('appnew.settings.company')}</dt><dd>{session?.companyName||t('appnew.settings.evaluationWorkspace')}</dd><dt>{t('appnew.settings.edition')}</dt><dd>{editionLabel(session?.edition)}</dd><dt>{t('appnew.settings.currentProduct')}</dt><dd>{setup?.productName||t('appnew.settings.notSetUp')}</dd><dt>{t('appnew.settings.session')}</dt><dd>{account?t('appnew.settings.registeredSession'):t('appnew.settings.evaluationSession')}</dd></dl></div></section><div className="ds-button-row"><button className="ds-button quiet" onClick={restart}>{t('appnew.settings.restartOnboarding')}</button><button className="ds-button primary" disabled={busy} onClick={signout}>{busy?t('appnew.settings.signingOut'):t('appnew.settings.signOutEvaluation')}</button></div></div>}
