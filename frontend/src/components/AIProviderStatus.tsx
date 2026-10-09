import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import client from '../api/client';

type Health = { status: string; db: string; llm_provider: string; embedding_provider: string };

export default function AIProviderStatus() {
  const { t } = useTranslation();
  const [health, setHealth] = useState<Health | null>(null);
  const [error, setError] = useState(false);
  useEffect(() => { if (window.datashieldDesktop) client.get<Health>('/health').then(value => setHealth(value.data)).catch(() => setError(true)); }, []);
  return <section className="ds-action-block"><h2>{t('appnew.settings.aiProvider.title')}</h2><div><dl><dt>{t('appnew.settings.aiProvider.service')}</dt><dd>{error?t('appnew.settings.aiProvider.unavailable'):health?t(`appnew.settings.aiProvider.status.${health.status}`,{defaultValue:health.status}):t('appnew.settings.aiProvider.loading')}</dd><dt>{t('appnew.settings.aiProvider.llm')}</dt><dd>{health?.llm_provider||'—'}</dd><dt>{t('appnew.settings.aiProvider.embeddings')}</dt><dd>{health?.embedding_provider||'—'}</dd></dl><p>{t('appnew.settings.aiProvider.note')}</p></div></section>;
}
