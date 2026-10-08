import { FormEvent, StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { getRuntimeHealth, localApiRequest } from './local-api';
import { type Locale, useLocale } from './i18n';
import './styles.css';
import { RemediationPage } from './RemediationPage';
import { FeedbackPanel } from './FeedbackPanel';
import { TodayPage } from './TodayPage';
import { UnderstandingPage } from './UnderstandingPage';

type Screen = 'welcome' | 'workspace' | 'intake' | 'today' | 'monitor' | 'findings' | 'actions' | 'twin' | 'settings';
type WorkspaceRef = { companyId: number; productId: number };
type RegulationEvent = { event: { event_id: string; payload?: { materiality?: string; topics?: string[] } }; regulation: { name?: string; jurisdiction?: string } };
const workspaceKey = 'datashield.desktop.workspace';

function savedWorkspace(): WorkspaceRef | null {
  try {
    const value = JSON.parse(window.localStorage.getItem(workspaceKey) ?? 'null');
    return Number.isInteger(value?.companyId) && Number.isInteger(value?.productId) ? value : null;
  } catch { return null; }
}

function App() {
  const { locale, setLocale, copy } = useLocale();
  const [screen, setScreen] = useState<Screen>('welcome');
  const [runtime, setRuntime] = useState<'checking' | 'connected' | 'offline'>('checking');
  const [workspaceKind, setWorkspaceKind] = useState<'developer' | 'enterprise'>('developer');
  const [workspaceError, setWorkspaceError] = useState(false);
  const [workspace, setWorkspace] = useState<WorkspaceRef | null>(savedWorkspace);
  const [selectedFinding, setSelectedFinding] = useState<number | null>(null);

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
      const next = { companyId: company.id, productId: product.id };
      window.localStorage.setItem(workspaceKey, JSON.stringify(next));
      setWorkspace(next);
      setScreen('intake');
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
      {screen === 'intake' && workspace && <ProductIntake copy={copy} workspace={workspace} onDone={() => setScreen('twin')} />}
      {screen === 'intake' && !workspace && <EmptyPage copy={copy} screen="twin" />}
      {screen === 'twin' && <TwinPage copy={copy} workspace={workspace} onIntake={() => setScreen('intake')} />}
      {screen === 'monitor' && <MonitorPage copy={copy} />}
      {screen === 'findings' && <FindingsPage copy={copy} workspace={workspace} initialFinding={selectedFinding} onRemediate={id => { setSelectedFinding(id); setScreen('actions'); }} />}
      {screen === 'actions' && <RemediationPage copy={copy} workspace={workspace} initialFinding={selectedFinding} onFinding={id => { setSelectedFinding(id); setScreen('findings'); }} />}
      {screen === 'today' && <TodayPage copy={copy} workspace={workspace} onNavigate={(page, id) => { setSelectedFinding(id ?? null); setScreen(page); }} />}
      {screen === 'settings' && <Settings copy={copy} />}
    </section>
  </main>;
}

function ProductIntake({ copy, workspace, onDone }: { copy: ReturnType<typeof useLocale>['copy']; workspace: WorkspaceRef; onDone: () => void }) {
  const [fact, setFact] = useState(''); const [saving, setSaving] = useState(false); const [error, setError] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError(false);
    try {
      await localApiRequest(`/api/v1/ui/understanding/products/${workspace.productId}/twin/facts`, 'POST', {
        company_id: workspace.companyId, group: 'features', fact: { name: fact, status: 'PRESENT', confidence: 0.8 }, note: 'Desktop onboarding',
      });
      onDone();
    } catch { setError(true); } finally { setSaving(false); }
  };
  return <section className="page business-page"><p className="eyebrow">{copy.intake.eyebrow}</p><h1>{copy.intake.title}</h1><p>{copy.intake.body}</p><form className="workspace-form" onSubmit={submit}><label>{copy.intake.fact}<input value={fact} required onChange={e => setFact(e.target.value)} placeholder={copy.intake.placeholder} /></label>{error && <p className="form-error">{copy.intake.error}</p>}<button className="primary" disabled={saving}>{saving ? copy.intake.saving : copy.intake.continue}</button></form><UnderstandingPage copy={copy} workspace={workspace} onDone={onDone} /></section>;
}

function TwinPage({ copy, workspace, onIntake }: { copy: ReturnType<typeof useLocale>['copy']; workspace: WorkspaceRef | null; onIntake: () => void }) {
  const [facts, setFacts] = useState<Array<{ id: number; group: string; name: string; status: string }>>([]);
  const [loaded, setLoaded] = useState(false);
  useEffect(() => {
    if (!workspace) return;
    void localApiRequest<{ facts?: Array<{ id: number; group: string; name: string; status: string }> }>(`/api/v1/ui/understanding/products/${workspace.productId}/twin?company_id=${workspace.companyId}`)
      .then(value => setFacts(value.facts ?? [])).finally(() => setLoaded(true));
  }, [workspace]);
  if (!workspace) return <EmptyPage copy={copy} screen="twin" />;
  const intakeButton = <button className="primary" onClick={onIntake}>{copy.understanding.title}</button>;
  return <section className="page empty"><h1>{copy.twin.title}</h1>{intakeButton}{!loaded ? <div className="empty-card"><p>{copy.twin.loading}</p></div> : facts.length === 0 ? <div className="empty-card"><p>{copy.twin.empty}</p></div> : <div className="settings-list">{facts.map(fact => <div key={fact.id}><strong>{fact.name}</strong><span>{fact.group} · {fact.status}</span></div>)}</div>}</section>;
}

function MonitorPage({ copy }: { copy: ReturnType<typeof useLocale>['copy'] }) {
  const [state, setState] = useState<{ scope: string; using_local_cache: boolean; last_success_at: string; last_error: string } | null>(null);
  const [events, setEvents] = useState<RegulationEvent[]>([]);
  const [syncing, setSyncing] = useState(false);
  const load = async () => {
    const [nextState, nextEvents] = await Promise.all([localApiRequest<typeof state>('/api/v1/local-regulations/status'), localApiRequest<typeof events>('/api/v1/local-regulations/events')]);
    setState(nextState); setEvents(nextEvents);
  };
  useEffect(() => { void load(); }, []);
  const sync = async () => { setSyncing(true); try { await localApiRequest('/api/v1/local-regulations/sync', 'POST'); } catch { /* status preserves offline cache reason */ } finally { setSyncing(false); await load(); } };
  return <section className="page"><h1>{copy.monitor.title}</h1><p>{state?.using_local_cache ? copy.monitor.offline : copy.monitor.body}</p><div className="settings-list"><div><strong>{copy.monitor.lastSync}</strong><span>{state?.last_success_at || copy.monitor.never}</span></div><div><strong>{copy.monitor.scope}</strong><span>{state?.scope || copy.monitor.loading}</span></div>{state?.last_error && <div><strong>{copy.monitor.status}</strong><span>{state.last_error}</span></div>}</div><button className="primary" disabled={syncing} onClick={() => void sync()}>{syncing ? copy.monitor.syncing : copy.monitor.sync}</button><div className="settings-list">{events.length ? events.map(item => <div key={item.event.event_id}><strong>{item.regulation.name || item.event.event_id}</strong><span>{item.regulation.jurisdiction || '—'} · {item.event.payload?.materiality || 'UNKNOWN'} · {(item.event.payload?.topics || []).join(', ')}</span></div>) : <div><span>{copy.monitor.empty}</span></div>}</div></section>;
}

function FindingsPage({ copy, workspace, initialFinding, onRemediate }: { copy: ReturnType<typeof useLocale>['copy']; workspace: WorkspaceRef | null; initialFinding: number | null; onRemediate: (id: number) => void }) {
  const [findings, setFindings] = useState<Array<{ id: number; title: string; impact_level: string; status: string; requirement_count: number; evidence_count: number; product_twin_version_id?: number }>>([]);
  const [message, setMessage] = useState(''); const [running, setRunning] = useState(false);
  const [detail, setDetail] = useState<{ finding: { id: number; status: string; title: string; applicability_summary: string; gap_summary: string; product_twin_version_id?: number; created_at: string }; requirements: Array<{ summary: string; regulation_name?: string; version_id?: number }>; legal_evidence: Array<{ regulation_name: string; article: string; heading: string; source_url: string }>; agent_run: { id: number; created_at: string } } | null>(null);
  useEffect(() => { if (workspace && initialFinding) void localApiRequest<typeof detail>(`/api/v1/findings/${initialFinding}?tenant_id=${workspace.companyId}`).then(setDetail).catch(() => setMessage(copy.findings.loadError)); }, [workspace, initialFinding]);
  const load = async () => { if (!workspace) return; try { setFindings(await localApiRequest<typeof findings>(`/api/v1/findings?tenant_id=${workspace.companyId}&product_id=${workspace.productId}`)); } catch { setMessage(copy.findings.loadError); } };
  useEffect(() => { void load(); }, [workspace]);
  const run = async () => { if (!workspace) return; setRunning(true); setMessage(''); try { const requirements = await localApiRequest<Array<{ id: number }>>('/api/v1/local-regulations/requirements'); if (!requirements.length) { setMessage(copy.findings.noRequirements); return; } const result = await localApiRequest<{ status: string; missing_context: unknown[]; finding_ids: number[] }>('/api/v1/tenant-agent/analyze', 'POST', { tenant_id: workspace.companyId, product_id: workspace.productId, trigger_type: 'MANUAL_SCAN', requirement_ids: requirements.map(item => item.id) }); setMessage(result.missing_context.length ? copy.findings.needsContext : result.finding_ids.length ? copy.findings.done : copy.findings.noApplicable); await load(); } catch { setMessage(copy.findings.runError); } finally { setRunning(false); } };
  if (!workspace) return <EmptyPage copy={copy} screen="findings" />;
  const open = async (id: number) => { try { setDetail(await localApiRequest<typeof detail>(`/api/v1/findings/${id}?tenant_id=${workspace.companyId}`)); } catch { setMessage(copy.findings.loadError); } };
  const remediationButton = detail?.finding.status === 'OPEN' ? <button className="primary" onClick={() => onRemediate(detail.finding.id)}>{copy.actions.create}</button> : null;
  const feedbackPanel = detail ? <FeedbackPanel key={detail.finding.id} copy={copy} workspace={workspace} findingId={detail.finding.id} /> : null;
  return <section className="page"><h1>{copy.findings.title}</h1>{remediationButton}<p>{copy.findings.body}</p><button className="primary" disabled={running} onClick={() => void run()}>{running ? copy.findings.running : copy.findings.run}</button>{message && <p className="form-error">{message}</p>}<div className="settings-list">{findings.length ? findings.map(item => <div key={item.id}><button className="quiet" onClick={() => void open(item.id)}>{item.title}</button><span>{item.impact_level} · {item.status} · {copy.findings.requirements}: {item.requirement_count} · {copy.findings.evidence}: {item.evidence_count} · {copy.findings.twin}: v{item.product_twin_version_id ?? '—'}</span></div>) : <div><span>{copy.findings.empty}</span></div>}</div>{detail && <div className="settings-list"><div><strong>{copy.findings.applicability}</strong><span>{detail.finding.applicability_summary}</span></div><div><strong>{copy.findings.gap}</strong><span>{detail.finding.gap_summary}</span></div><div><strong>{copy.findings.runRef}</strong><span>#{detail.agent_run.id} · {detail.agent_run.created_at}</span></div><div><strong>{copy.findings.requirements}</strong><span>{detail.requirements.map(item => `${item.regulation_name || ''} ${item.summary}`).join('；') || copy.findings.noEvidence}</span></div><div><strong>{copy.findings.evidence}</strong><span>{detail.legal_evidence.map(item => `${item.regulation_name} ${item.article} ${item.heading} ${item.source_url}`).join('；') || copy.findings.noEvidence}</span></div></div>}{feedbackPanel}</section>;
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
