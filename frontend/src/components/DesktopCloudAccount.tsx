import { FormEvent, useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useTranslation } from 'react-i18next';
import client from '../api/client';
import { createCompany, listCompanies } from '../api';
import { writeSession, type Edition } from '../features/auth/session';
import { useNavigate } from 'react-router-dom';

type IdentityView = {
  userId?: number;
  email: string;
  name?: string;
  emailVerified: boolean;
  organization?: { id: number; name: string; edition: Edition; role: string };
  verificationRequired: boolean;
};

export default function DesktopCloudAccount({ mode, edition }: { mode: 'login' | 'signup'; edition: Edition }) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [baseUrl, setBaseUrl] = useState('');
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [organization, setOrganization] = useState('');
  const [code, setCode] = useState('');
  const [needsVerification, setNeedsVerification] = useState(false);
  const [resettingPassword, setResettingPassword] = useState(false);
  const [resetCodeSent, setResetCodeSent] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  useEffect(() => {
    client.get<{ base_url: string }>('/v1/local-regulations/configuration')
      .then(({ data }) => setBaseUrl(data.base_url ? `${data.base_url.replace(/\/$/, '')}/identity` : ''))
      .catch(() => setBaseUrl(''));
  }, []);

  const finishLogin = async (account: IdentityView) => {
    const workspaceName = account.organization?.name || organization.trim() || t('appnew.desktopAccount.privateWorkspace');
    const existing = await listCompanies();
    const local = existing.find(company => company.name === workspaceName)
      || await createCompany({ name: workspaceName, industry: '', country: '', target_markets: [], business_model: 'offline' });
    writeSession({ name: account.name || account.email.split('@')[0], email: account.email,
      edition: account.organization?.edition || edition, companyName: workspaceName, companyId: local.id });
    navigate('/onboarding/understand');
  };

  const submit = async (event: FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      if (!baseUrl) throw new Error(t('appnew.desktopAccount.endpointMissing'));
      if (needsVerification) {
        await invoke<boolean>('cloud_identity_verify_email', { input: { baseUrl, email, code } });
        setNeedsVerification(false); setCode('');
        navigate('/login');
        return;
      }
      if (resettingPassword && !resetCodeSent) {
        await invoke('cloud_identity_password_reset_request', { input: { baseUrl, email } });
        setResetCodeSent(true);
        return;
      }
      if (resettingPassword) {
        await invoke('cloud_identity_password_reset_confirm', { input: { baseUrl, email, code, newPassword: password } });
        setResettingPassword(false); setResetCodeSent(false); setCode(''); setPassword('');
        setNotice(t('appnew.desktopAccount.passwordResetDone'));
        return;
      }
      if (mode === 'signup') {
        const account = await invoke<IdentityView>('cloud_identity_register', { input: {
          baseUrl, email, password, name, organizationName: organization, edition,
        } });
        if (account.verificationRequired) { setNeedsVerification(true); return; }
        await finishLogin(account);
      } else {
        const account = await invoke<IdentityView>('cloud_identity_login', { input: { baseUrl, email, password } });
        await finishLogin(account);
      }
    } catch (err: any) {
      setError(typeof err === 'string' ? err : err?.response?.data?.detail || err?.message || t('appnew.desktopAccount.requestFailed'));
    } finally { setBusy(false); }
  };

  return <section className="ds-action-block" aria-labelledby="cloud-account-title">
    <h2 id="cloud-account-title">{mode === 'signup' ? t('appnew.desktopAccount.registerTitle') : t('appnew.desktopAccount.loginTitle')}</h2>
    <p>{t('appnew.desktopAccount.privacy')}</p>
    <form onSubmit={submit}>
      {!needsVerification && !resettingPassword && <>
        {mode === 'signup' && <label>{t('appnew.auth.name')}<input required maxLength={200} value={name} onChange={e => setName(e.target.value)} autoComplete="name" /></label>}
        <label>{t('appnew.auth.email')}<input required type="email" maxLength={320} value={email} onChange={e => setEmail(e.target.value)} autoComplete="email" /></label>
        <label>{t('appnew.auth.password')}<input required type="password" minLength={12} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} autoComplete={mode === 'signup' ? 'new-password' : 'current-password'} /></label>
        {mode === 'signup' && <label>{t('appnew.auth.workspaceName')}<input required maxLength={200} value={organization} onChange={e => setOrganization(e.target.value)} /></label>}
      </>}
      {(needsVerification || (resettingPassword && resetCodeSent)) && <label>{t('appnew.desktopAccount.verificationCode')}<input required inputMode="numeric" pattern="[0-9]{6}" minLength={6} maxLength={6} value={code} onChange={e => setCode(e.target.value)} autoComplete="one-time-code" /></label>}
      {resettingPassword && <label>{t('appnew.desktopAccount.newPassword')}<input required type="password" minLength={12} maxLength={128} value={password} onChange={e => setPassword(e.target.value)} autoComplete="new-password" /></label>}
      {!baseUrl && <p role="status" className="ds-inline-error">{t('appnew.desktopAccount.endpointMissing')}</p>}
      {error && <p role="alert" className="ds-inline-error">{error}</p>}
      {notice && <p role="status" className="ds-cloud-notice">{notice}</p>}
      <button className="ds-button primary" disabled={busy || !baseUrl}>{busy ? t('appnew.desktopAccount.working') : needsVerification ? t('appnew.desktopAccount.verify') : resettingPassword ? resetCodeSent ? t('appnew.desktopAccount.resetPassword') : t('appnew.desktopAccount.requestReset') : mode === 'signup' ? t('appnew.desktopAccount.register') : t('appnew.desktopAccount.login')}</button>
    </form>
    {needsVerification && <button className="ds-button quiet" type="button" disabled={busy} onClick={async () => {
      setBusy(true); setError('');
      try { await invoke('cloud_identity_resend_verification', { input: { baseUrl, email } }); setNotice(t('appnew.desktopAccount.verificationResent')); }
      catch (err: any) { setError(typeof err === 'string' ? err : t('appnew.desktopAccount.requestFailed')); }
      finally { setBusy(false); }
    }}>{t('appnew.desktopAccount.resendVerification')}</button>}
    {mode === 'login' && !needsVerification && <button className="ds-button quiet" type="button" onClick={() => { setResettingPassword(value => !value); setResetCodeSent(false); setCode(''); setError(''); }}>{resettingPassword ? t('appnew.desktopAccount.backToLogin') : t('appnew.desktopAccount.forgotPassword')}</button>}
  </section>;
}
