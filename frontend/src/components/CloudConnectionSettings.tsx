import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import client from '../api/client';

type SyncStatus = { offline?: boolean; last_success_at?: string; last_attempt_at?: string; last_error?: string; cursor?: number };

export default function CloudConnectionSettings() {
  const { t, i18n } = useTranslation();
  const [url, setUrl] = useState('');
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');
  const load = async () => {
    try {
      const [configuration, current] = await Promise.all([
        client.get<{ base_url: string }>('/v1/local-regulations/configuration'),
        client.get<SyncStatus>('/v1/local-regulations/status'),
      ]);
      setUrl(configuration.data.base_url || '');
      setStatus(current.data);
    } catch (err: any) { setError(err?.response?.data?.detail || err?.message || t('appnew.settings.cloud.loadError')); }
  };
  useEffect(() => { if (window.datashieldDesktop) void load(); }, []);
  const save = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setError(''); setNotice('');
    try {
      const response = await client.put<{ base_url: string }>('/v1/local-regulations/configuration', { base_url: url });
      setUrl(response.data.base_url); setNotice(t('appnew.settings.cloud.saved'));
    } catch (err: any) { setError(err?.response?.data?.detail || err?.message || t('appnew.settings.cloud.saveError')); }
    finally { setBusy(false); }
  };
  const sync = async () => {
    setBusy(true); setError(''); setNotice('');
    try {
      const response = await client.post<{ status: SyncStatus }>('/v1/local-regulations/sync');
      setStatus(response.data.status); setNotice(t('appnew.settings.cloud.syncDone'));
    } catch (err: any) {
      setError(err?.response?.data?.detail || err?.message || t('appnew.settings.cloud.syncError'));
      await client.get<SyncStatus>('/v1/local-regulations/status').then(value => setStatus(value.data)).catch(() => {});
    } finally { setBusy(false); }
  };
  const syncedAt = status?.last_success_at ? new Intl.DateTimeFormat(i18n.language === 'zh' ? 'zh-CN' : 'en-US', { dateStyle: 'medium', timeStyle: 'short' }).format(new Date(status.last_success_at)) : '';
  return <section className="ds-action-block ds-cloud-settings"><h2>{t('appnew.settings.cloud.title')}</h2><div>
    <p>{t('appnew.settings.cloud.description')}</p>
    <form onSubmit={save}><label>{t('appnew.settings.cloud.endpoint')}<input type="url" value={url} onChange={event => setUrl(event.target.value)} placeholder="https://cloud.example.com" /></label><div className="ds-button-row"><button className="ds-button quiet" disabled={busy}>{busy?t('appnew.settings.cloud.saving'):t('appnew.settings.cloud.save')}</button><button className="ds-button primary" type="button" disabled={busy||!url} onClick={sync}>{busy?t('appnew.settings.cloud.syncing'):t('appnew.settings.cloud.sync')}</button></div></form>
    <dl><dt>{t('appnew.settings.cloud.serviceStatus')}</dt><dd>{!url?t('appnew.settings.cloud.notConfigured'):status?.last_success_at?t('appnew.settings.cloud.lastSync',{time:syncedAt}):status?.offline?t('appnew.settings.cloud.offlineCache'):t('appnew.settings.cloud.notSynced')}</dd><dt>{t('appnew.settings.cloud.localRequirements')}</dt><dd>{status?.cursor??0}</dd></dl>
    <p className="ds-cloud-privacy">{t('appnew.settings.cloud.privacy')}</p>
    {notice&&<p role="status" className="ds-cloud-notice">{notice}</p>}{error&&<p role="alert" className="ds-inline-error">{error}</p>}
  </div></section>;
}
