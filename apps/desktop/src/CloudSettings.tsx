import { useEffect, useState } from 'react';
import { localApiRequest } from './local-api';
import type { Copy } from './i18n';
export function CloudSettings({ copy }: { copy: Copy }) {
  const c = copy.settings; const [url, setUrl] = useState(''); const [busy, setBusy] = useState(false); const [message, setMessage] = useState('');
  useEffect(() => { void localApiRequest<{ base_url: string }>('/api/v1/local-regulations/configuration').then(v => setUrl(v.base_url)).catch(() => setMessage(c.error)); }, []);
  return <form className="workspace-form" onSubmit={e => { e.preventDefault(); setBusy(true); setMessage(''); void localApiRequest('/api/v1/local-regulations/configuration', 'PUT', { base_url: url }).then(() => setMessage(c.saved)).catch(() => setMessage(c.error)).finally(() => setBusy(false)); }}><label>{c.cloud}<input required type="url" value={url} onChange={e => setUrl(e.target.value)} placeholder="https://" /></label><p>{c.cloudHelp}</p><button disabled={busy} className="primary">{c.save}</button>{message && <p role="status">{message}</p>}</form>;
}
