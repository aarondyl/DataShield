import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useTranslation } from 'react-i18next';
import client from '../api/client';

type IdentityView = { email: string; name?: string; organization?: { id: number; name: string; edition: string; role: string } };

export default function CloudIdentitySettings() {
  const { t } = useTranslation();
  const [baseUrl, setBaseUrl] = useState('');
  const [account, setAccount] = useState<IdentityView | null>(null);
  const [status, setStatus] = useState<'checking' | 'signed-in' | 'signed-out' | 'unavailable'>('checking');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');

  const load = async () => {
    try {
      const { data } = await client.get<{ base_url: string }>('/v1/local-regulations/configuration');
      const endpoint = data.base_url ? `${data.base_url.replace(/\/$/, '')}/identity` : '';
      setBaseUrl(endpoint);
      if (!endpoint) { setStatus('unavailable'); return; }
      const value = await invoke<IdentityView>('cloud_identity_me', { input: { baseUrl: endpoint } });
      setAccount(value); setStatus('signed-in');
    } catch (error) {
      setAccount(null);
      setStatus(String(error).includes('IDENTITY_SESSION_MISSING') ? 'signed-out' : 'unavailable');
    }
  };
  useEffect(() => { void load(); }, []);

  const signOut = async () => {
    setBusy(true); setMessage('');
    try { await invoke('cloud_identity_logout', { input: { baseUrl } }); setAccount(null); setStatus('signed-out'); setMessage(t('appnew.desktopAccount.signedOut')); }
    catch (error) { setMessage(typeof error === 'string' ? error : t('appnew.desktopAccount.signOutError')); }
    finally { setBusy(false); }
  };

  return <section className="ds-action-block"><h2>{t('appnew.desktopAccount.accountSettings')}</h2><div>
    <p>{account ? t('appnew.desktopAccount.signedIn', { email: account.email, organization: account.organization?.name || '' }) : status === 'unavailable' ? t('appnew.desktopAccount.statusUnavailable') : status === 'checking' ? t('appnew.desktopAccount.checking') : t('appnew.desktopAccount.signedOutState')}</p>
    {account && <button className="ds-button quiet" disabled={busy} onClick={signOut}>{busy ? t('appnew.settings.signingOut') : t('appnew.settings.logOut')}</button>}
    {message && <p role="status" className="ds-cloud-notice">{message}</p>}
  </div></section>;
}
