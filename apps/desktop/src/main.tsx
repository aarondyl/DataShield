import { FormEvent, StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { getRuntimeHealth, localApiRequest } from './local-api';
import { type Locale, useLocale } from './i18n';
import './styles.css';

type Screen = 'welcome' | 'workspace' | 'today' | 'monitor' | 'findings' | 'actions' | 'twin' | 'settings';

function App() {
  const { locale, setLocale, copy } = useLocale();
  const [screen, setScreen] = useState<Screen>('welcome');
  const [runtime, setRuntime] = useState<'checking' | 'connected' | 'offline'>('checking');
  const [workspaceKind, setWorkspaceKind] = useState<'developer' | 'enterprise'>('developer');
  const [workspaceError, setWorkspaceError] = useState(false);

  const checkRuntime = async () => {
    setRuntime('checking');
    try {
      const result = await getRuntimeHealth();
      setRuntime(result.ok ? 'connected' : 'offline');
    } catch {
      setRuntime('offline');
    }
  };
  useEffect(() => { void checkRuntime(); }, []);

  const navScreens: Screen[] = ['today', 'monitor', 'findings', 'actions', 'twin', 'settings'];
  const nav = navScreens.map((key, index) => ({ key, label: copy.nav[index] }));
  const statusText = runtime === 'connected' ? copy.status.connected : runtime === 'checking' ? copy.status.checking : copy.status.offline;

  const createWorkspace = async (companyName: string, productName: string, description: string) => {
    setWorkspaceError(false);
    try {
      const company = await localApiRequest<{ id: number }>('/api/companies', 'POST', { name: companyName });
      const product = await localApiRequest<{ id: number }>('/api/products', 'POST', { company_id: company.id, name: productName, description });
      window.localStorage.setItem('datashield.desktop.workspace', JSON.stringify({ companyId: company.id, productId: product.id }));
      setScreen('twin');
    } catch { setWorkspaceError(true); }
  };

  return <main className="app-shell">
    <aside className="sidebar">
      <div className="brand"><span className="brand-mark">D</span><span>{copy.productName}</span></div>
      <p className="preview-tag">{copy.labels.demo}</p>
      <nav aria-label="主导航">
        {nav.map(item => <button key={item.key} className={screen === item.key ? 'nav-item active' : 'nav-item'} onClick={() => setScreen(item.key)}>{item.label}</button>)}
      </nav>
      <div className={'runtime ' + runtime}><span aria-hidden="true" />{statusText}<button onClick={() => void checkRuntime()}>{copy.labels.retry}</button></div>
    </aside>
    <section className="content">
      <header><div className="locale" role="group" aria-label={copy.settings.language}>
        {(['zh-CN', 'en-US'] as Locale[]).map(value => <button key={value} className={locale === value ? 'selected' : ''} onClick={() => setLocale(value)}>{value === 'zh-CN' ? copy.labels.chinese : copy.labels.english}</button>)}
      </div></header>
      {screen === 'welcome' && <Welcome copy={copy} onCreate={() => setScreen('workspace')} />}
      {screen === 'workspace' && <Workspace copy={copy} kind={workspaceKind} setKind={setWorkspaceKind} error={workspaceError} onContinue={createWorkspace} />}
      {(['today', 'monitor', 'findings', 'actions', 'twin'] as Screen[]).includes(screen) && <EmptyPage copy={copy} screen={screen as 'today' | 'monitor' | 'findings' | 'actions' | 'twin'} />}
      {screen === 'settings' && <Settings copy={copy} />}
    </section>
  </main>;
}

function Welcome({ copy, onCreate }: { copy: ReturnType<typeof useLocale>['copy']; onCreate: () => void }) {
  return <section className="hero"><p className="eyebrow">{copy.welcome.eyebrow}</p><h1>{copy.welcome.title}</h1><p>{copy.welcome.body}</p><div className="buttons"><button className="primary" onClick={onCreate}>{copy.welcome.create}</button><button className="quiet">{copy.welcome.privacy}</button></div></section>;
}

function Workspace({ copy, kind, setKind, error, onContinue }: { copy: ReturnType<typeof useLocale>['copy']; kind: 'developer' | 'enterprise'; setKind: (kind: 'developer' | 'enterprise') => void; error: boolean; onContinue: (company: string, product: string, description: string) => Promise<void> }) {
  const [company, setCompany] = useState(''); const [product, setProduct] = useState(''); const [description, setDescription] = useState(''); const [submitting, setSubmitting] = useState(false);
  const submit = async (event: FormEvent) => { event.preventDefault(); setSubmitting(true); await onContinue(company, product, description); setSubmitting(false); };
  return <section className="page"><h1>{copy.workspace.title}</h1><p>{copy.workspace.body}</p><div className="cards">
    {(['developer', 'enterprise'] as const).map(option => <button className={'card ' + (kind === option ? 'chosen' : '')} key={option} onClick={() => setKind(option)}><strong>{copy.workspace[option]}</strong><span>{copy.workspace[`${option}Body`]}</span></button>)}
  </div><form className="workspace-form" onSubmit={submit}><label>{copy.workspace.workspaceName}<input value={company} required onChange={e => setCompany(e.target.value)} /></label><label>{copy.workspace.productName}<input value={product} required onChange={e => setProduct(e.target.value)} /></label><label>{copy.workspace.description}<textarea value={description} onChange={e => setDescription(e.target.value)} /></label>{error && <p className="form-error">{copy.workspace.createError}</p>}<button className="primary" disabled={submitting}>{submitting ? copy.workspace.creating : copy.workspace.continue}</button></form></section>;
}

function EmptyPage({ copy, screen }: { copy: ReturnType<typeof useLocale>['copy']; screen: 'today' | 'monitor' | 'findings' | 'actions' | 'twin' }) {
  const section = copy[screen];
  return <section className="page empty"><h1>{section.title}</h1><div className="empty-card"><p>{section.empty}</p></div></section>;
}

function Settings({ copy }: { copy: ReturnType<typeof useLocale>['copy'] }) {
  return <section className="page"><h1>{copy.settings.title}</h1><div className="settings-list"><div><strong>{copy.settings.ai}</strong><span>DESKTOP_AI_MODE</span></div><div><strong>{copy.settings.privacy}</strong><span>Local SQLite · Local FastAPI</span></div><div><strong>{copy.settings.update}</strong><span>Tauri updater（后续阶段）</span></div></div></section>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
