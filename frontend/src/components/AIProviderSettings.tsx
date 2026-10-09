import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useTranslation } from 'react-i18next';
import client from '../api/client';

type Provider = 'mock' | 'cloud' | 'byok' | 'ollama';
type Config = { provider: Provider; baseUrl: string; model: string; cloudConsent: boolean; keyConfigured: boolean };

const defaults: Config = { provider: 'mock', baseUrl: 'https://api.deepseek.com', model: 'deepseek-flash', cloudConsent: false, keyConfigured: false };

export default function AIProviderSettings() {
  const { t } = useTranslation();
  const [config, setConfig] = useState<Config>(defaults);
  const [apiKey, setApiKey] = useState('');
  const [models, setModels] = useState<string[]>([]);
  const [cloudBaseUrl, setCloudBaseUrl] = useState('');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [error, setError] = useState('');
  const [restartRequired, setRestartRequired] = useState(false);

  useEffect(() => {
    if (!window.datashieldDesktop) return;
    Promise.all([
      invoke<Config>('get_ai_provider_config'),
      client.get<{ base_url?: string }>('/v1/local-regulations/configuration').catch(() => null),
    ]).then(([saved, endpoint]) => {
      const cloudRoot = endpoint?.data.base_url?.replace(/\/$/, '');
      const identityUrl = cloudRoot ? `${cloudRoot}/identity` : '';
      setCloudBaseUrl(identityUrl);
      setConfig(saved.provider === 'cloud' && (!saved.baseUrl || saved.baseUrl === 'https://api.deepseek.com')
        ? { ...saved, baseUrl: identityUrl } : saved);
    }).catch(() => setError(t('appnew.settings.aiProvider.loadError')));
  }, [t]);

  const update = (patch: Partial<Config>) => setConfig(current => ({ ...current, ...patch }));
  const nativeError = (err: unknown) => {
    const code = String(err).replace(/^Error:\s*/, '').trim();
    return t(`appnew.settings.aiProvider.errors.${code}`, { defaultValue: code });
  };
  const save = async () => {
    setBusy(true); setError(''); setMessage('');
    try {
      const next = await invoke<Config>('set_ai_provider_config', { update: { ...config, apiKey: apiKey || null } });
      setConfig(next); setApiKey(''); setRestartRequired(true); setMessage(t('appnew.settings.aiProvider.saved'));
    } catch (err: any) { setError(nativeError(err)); }
    finally { setBusy(false); }
  };
  const loadOllamaModels = async () => {
    setBusy(true); setError('');
    try {
      const response = await client.get<{ models: string[] }>('/ai/provider/ollama-models');
      setModels(response.data.models);
      if (response.data.models[0] && !response.data.models.includes(config.model)) update({ model: response.data.models[0] });
      if (!response.data.models.length) setMessage(t('appnew.settings.aiProvider.noOllamaModels'));
    } catch (err: any) { setError(err?.response?.data?.detail || err.message); }
    finally { setBusy(false); }
  };
  const test = async () => {
    setBusy(true); setError(''); setMessage('');
    try {
      const response = await client.post<{ provider: string; model: string }>('/ai/provider/test', {});
      setMessage(t('appnew.settings.aiProvider.testOk', { provider: response.data.provider, model: response.data.model }));
    } catch (err: any) { setError(err?.response?.data?.detail || err.message); }
    finally { setBusy(false); }
  };
  const deleteKey = async () => {
    setBusy(true); setError(''); setMessage('');
    try {
      await invoke('delete_ai_provider_key');
      setConfig(current => ({ ...current, keyConfigured: false }));
      setRestartRequired(true); setMessage(t('appnew.settings.aiProvider.keyDeleted'));
    } catch (err: any) { setError(nativeError(err)); }
    finally { setBusy(false); }
  };

  return <section className="ds-action-block">
    <h2>{t('appnew.settings.aiProvider.configureTitle')}</h2>
    <div className="ds-ai-provider-settings">
      <label>{t('appnew.settings.aiProvider.mode')}<select value={config.provider} onChange={e => { const provider = e.target.value as Provider; update({ provider, model: provider === 'ollama' ? '' : provider === 'cloud' ? 'deepseek-flash' : config.model || 'deepseek-flash', baseUrl: provider === 'ollama' ? 'http://127.0.0.1:11434/v1' : provider === 'cloud' ? cloudBaseUrl : 'https://api.deepseek.com', cloudConsent: provider === 'mock' || provider === 'ollama' ? false : config.cloudConsent }); setRestartRequired(false); }}>
        <option value="mock">{t('appnew.settings.aiProvider.mock')}</option>
        <option value="cloud">{t('appnew.settings.aiProvider.cloud')}</option>
        <option value="byok">{t('appnew.settings.aiProvider.byok')}</option>
        <option value="ollama">{t('appnew.settings.aiProvider.ollama')}</option>
      </select></label>
      {config.provider !== 'mock' && <>
        {config.provider === 'byok' && <label>{t('appnew.settings.aiProvider.endpoint')}<input value={config.baseUrl} onChange={e => update({ baseUrl: e.target.value })} placeholder="https://api.deepseek.com" autoComplete="url" /></label>}
        {config.provider === 'cloud' && <p>{t('appnew.settings.aiProvider.cloudHelp')} <code>{config.baseUrl || t('appnew.settings.aiProvider.cloudUnavailable')}</code></p>}
        {config.provider === 'ollama' && <p>{t('appnew.settings.aiProvider.ollamaHelp')} <code>http://127.0.0.1:11434</code></p>}
        <label>{t('appnew.settings.aiProvider.model')}<input value={config.model} onChange={e => update({ model: e.target.value })} placeholder={config.provider === 'ollama' ? '模型名称' : 'deepseek-flash'} autoComplete="off" /></label>
      </>}
      {config.provider === 'byok' && <>
        <label>{t('appnew.settings.aiProvider.apiKey')}<input type="password" value={apiKey} onChange={e => setApiKey(e.target.value)} placeholder={config.keyConfigured ? t('appnew.settings.aiProvider.keySaved') : t('appnew.settings.aiProvider.keyRequired')} autoComplete="new-password" /></label>
        <label className="ds-ai-consent"><input type="checkbox" checked={config.cloudConsent} onChange={e => update({ cloudConsent: e.target.checked })} />{t('appnew.settings.aiProvider.consent')}</label>
        <p>{t('appnew.settings.aiProvider.keyStorage')}</p>
        {config.keyConfigured && <button className="ds-button quiet" disabled={busy} onClick={deleteKey}>{t('appnew.settings.aiProvider.deleteKey')}</button>}
      </>}
      {config.provider === 'cloud' && <label className="ds-ai-consent"><input type="checkbox" checked={config.cloudConsent} onChange={e => update({ cloudConsent: e.target.checked })} />{t('appnew.settings.aiProvider.cloudConsent')}</label>}
      {config.provider === 'ollama' && <button className="ds-button quiet" disabled={busy || restartRequired} onClick={loadOllamaModels}>{t('appnew.settings.aiProvider.loadModels')}</button>}
      {models.length > 0 && config.provider === 'ollama' && <label>{t('appnew.settings.aiProvider.availableModels')}<select value={config.model} onChange={e => update({ model: e.target.value })}>{models.map(model => <option key={model} value={model}>{model}</option>)}</select></label>}
      {restartRequired && <p role="status">{t('appnew.settings.aiProvider.restart')}</p>}
      {error && <p role="alert">{error}</p>}{message && <p role="status">{message}</p>}
      <div className="ds-button-row"><button className="ds-button primary" disabled={busy} onClick={save}>{busy ? t('appnew.settings.aiProvider.saving') : t('appnew.settings.aiProvider.save')}</button><button className="ds-button quiet" disabled={busy || restartRequired || config.provider === 'mock'} onClick={test}>{t('appnew.settings.aiProvider.test')}</button></div>
    </div>
  </section>;
}
