import { FormEvent, StrictMode, useEffect, useState } from 'react';
import { createRoot } from 'react-dom/client';
import { getRuntimeHealth, localApiRequest } from './local-api';
import { type Locale, useLocale } from './i18n';
import './styles.css';
import { RemediationPage } from './RemediationPage';
import { FeedbackPanel } from './FeedbackPanel';
import { TodayPage } from './TodayPage';
import { UnderstandingPage } from './UnderstandingPage';
import { FindingDetail, type FindingDetailData } from './FindingDetail';
import { TwinPage } from './TwinPage';
import { CloudSettings } from './CloudSettings';
import { MonitorPage } from './MonitorPage';

type Screen = 'welcome' | 'workspace' | 'intake' | 'today' | 'monitor' | 'findings' | 'actions' | 'twin' | 'settings';
type WorkspaceRef = { companyId: number; productId: number };
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
      {screen === 'welcome' && <Welcome copy={copy} onCreate={() => setScreen('workspace')} onPrivacy={() => setScreen('settings')} />}
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
  const [group, setGroup] = useState('features'); const [factStatus, setFactStatus] = useState('PRESENT');
  const [fact, setFact] = useState(''); const [saving, setSaving] = useState(false); const [error, setError] = useState(false);
  const submit = async (event: FormEvent) => {
    event.preventDefault(); setSaving(true); setError(false);
    try {
      await localApiRequest(`/api/v1/ui/understanding/products/${workspace.productId}/twin/facts`, 'POST', {
        company_id: workspace.companyId, group, fact: { name: fact, status: factStatus, confidence: 0.8 }, note: 'Desktop user-confirmed fact',
      });
      onDone();
    } catch { setError(true); } finally { setSaving(false); }
  };
  return <section className="page business-page"><p className="eyebrow">{copy.intake.eyebrow}</p><h1>{copy.intake.title}</h1><p>{copy.intake.body}</p><form className="workspace-form" onSubmit={submit}><label>{copy.intake.group}<select value={group} onChange={e => setGroup(e.target.value)}>{Object.entries(copy.twin.groups).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label><label>{copy.intake.fact}<input value={fact} required onChange={e => setFact(e.target.value)} placeholder={copy.intake.placeholder} /></label><label>{copy.intake.status}<select value={factStatus} onChange={e => setFactStatus(e.target.value)}>{Object.entries(copy.twin.states).map(([key, label]) => <option key={key} value={key}>{label}</option>)}</select></label>{error && <p className="form-error">{copy.intake.error}</p>}<button className="primary" disabled={saving}>{saving ? copy.intake.saving : copy.intake.continue}</button></form><UnderstandingPage copy={copy} workspace={workspace} onDone={onDone} /></section>;
}



function FindingsPage({ copy, workspace, initialFinding, onRemediate }: { copy: ReturnType<typeof useLocale>['copy']; workspace: WorkspaceRef | null; initialFinding: number | null; onRemediate: (id: number) => void }) {
  const [findings, setFindings] = useState<Array<{ id: number; title: string; impact_level: string; status: string; requirement_count: number; evidence_count: number; product_twin_version_id?: number }>>([]);
  const [message, setMessage] = useState(''); const [running, setRunning] = useState(false);
  const [detail, setDetail] = useState<FindingDetailData | null>(null);
  useEffect(() => { if (workspace && initialFinding) void localApiRequest<typeof detail>(`/api/v1/findings/${initialFinding}?tenant_id=${workspace.companyId}`).then(setDetail).catch(() => setMessage(copy.findings.loadError)); }, [workspace, initialFinding]);
  const load = async () => { if (!workspace) return; try { setFindings(await localApiRequest<typeof findings>(`/api/v1/findings?tenant_id=${workspace.companyId}&product_id=${workspace.productId}`)); } catch { setMessage(copy.findings.loadError); } };
  useEffect(() => { void load(); }, [workspace]);
  const run = async () => { if (!workspace) return; setRunning(true); setMessage(''); try { const requirements = await localApiRequest<Array<{ id: number }>>('/api/v1/local-regulations/requirements'); if (!requirements.length) { setMessage(copy.findings.noRequirements); return; } const result = await localApiRequest<{ status: string; missing_context: unknown[]; finding_ids: number[] }>('/api/v1/tenant-agent/analyze', 'POST', { tenant_id: workspace.companyId, product_id: workspace.productId, trigger_type: 'MANUAL_SCAN', requirement_ids: requirements.map(item => item.id) }); setMessage(result.status === 'FAILED' ? copy.findings.runError : result.missing_context.length ? copy.findings.needsContext : result.finding_ids.length ? copy.findings.done : copy.findings.noApplicable); await load(); } catch { setMessage(copy.findings.runError); } finally { setRunning(false); } };
  if (!workspace) return <EmptyPage copy={copy} screen="findings" />;
  const open = async (id: number) => { try { setDetail(await localApiRequest<typeof detail>(`/api/v1/findings/${id}?tenant_id=${workspace.companyId}`)); } catch { setMessage(copy.findings.loadError); } };
  const remediationButton = detail?.finding.status === 'OPEN' ? <button className="primary" onClick={() => onRemediate(detail.finding.id)}>{copy.actions.create}</button> : null;
  const feedbackPanel = detail ? <FeedbackPanel key={detail.finding.id} copy={copy} workspace={workspace} findingId={detail.finding.id} onApplied={() => { void load(); void open(detail.finding.id); }} /> : null;
  return <section className="page"><h1>{copy.findings.title}</h1>{remediationButton}<p>{copy.findings.body}</p><button className="primary" disabled={running} onClick={() => void run()}>{running ? copy.findings.running : copy.findings.run}</button>{message && <p className="form-error">{message}</p>}<div className="settings-list">{findings.length ? findings.map(item => <div key={item.id}><button className="quiet" onClick={() => void open(item.id)}>{item.title}</button><span>{copy.findings.risks[item.impact_level as keyof typeof copy.findings.risks] ?? item.impact_level} · {copy.findings.states[item.status as keyof typeof copy.findings.states] ?? item.status} · {copy.findings.requirements}: {item.requirement_count} · {copy.findings.evidence}: {item.evidence_count} · {copy.findings.twin}: #{item.product_twin_version_id ?? '—'}</span></div>) : <div><span>{copy.findings.empty}</span></div>}</div>{detail && <FindingDetail copy={copy} detail={detail} />}{feedbackPanel}</section>;
}

function Welcome({ copy, onCreate, onPrivacy }: { copy: ReturnType<typeof useLocale>['copy']; onCreate: () => void; onPrivacy: () => void }) {
  return <section className="hero"><p className="eyebrow">{copy.welcome.eyebrow}</p><h1>{copy.welcome.title}</h1><p>{copy.welcome.body}</p><div className="buttons"><button className="primary" onClick={onCreate}>{copy.welcome.create}</button><button className="quiet" onClick={onPrivacy}>{copy.welcome.privacy}</button></div></section>;
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
  return <section className="page"><h1>{copy.settings.title}</h1><CloudSettings copy={copy} /><div className="settings-list"><div><strong>{copy.settings.ai}</strong><span>{copy.settings.aiBoundary}</span></div><div><strong>{copy.settings.privacy}</strong><span>{copy.settings.privacyBody}</span></div><div><strong>{copy.settings.update}</strong><span>{copy.settings.updateBody}</span></div></div></section>;
}

createRoot(document.getElementById('root')!).render(<StrictMode><App /></StrictMode>);
