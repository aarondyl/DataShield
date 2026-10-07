import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import client from '../../api/client';
import Spinner from '../../components/Spinner';
import LanguageSwitcher from '../../components/LanguageSwitcher';

const KEY_STORAGE = 'datashield.admin.key';

type Tab = 'overview' | 'users' | 'workspaces' | 'regulations';

interface Overview {
  users: number;
  companies: number;
  products: number;
  analysis_runs: number;
  tenant_agent_runs: number;
  findings: number;
  regulations: number;
  legal_units: number;
  active_sessions: number;
}

interface AdminUser {
  id: number;
  email: string;
  display_name: string;
  company_id: number;
  company_name: string;
  edition: string;
  email_verified: boolean;
  disabled: boolean;
  created_at: string | null;
  last_login_at: string | null;
  active_sessions: number;
}

interface AdminCompany {
  id: number;
  name: string;
  business_model: string;
  products: number;
  users: string[];
  created_at: string | null;
}

interface AdminRegulation {
  id: number;
  name: string;
  short_name: string;
  official_identifier: string;
  jurisdiction: string;
  status: string;
  versions: number;
  legal_units: number;
  requirements: number;
}

type Confirm =
  | { kind: 'resetPassword'; user: AdminUser }
  | { kind: 'reseed' }
  | { kind: 'demoReset' }
  | null;

function adminGet<T>(path: string, key: string) {
  return client.get<T>(`/v1/admin${path}`, { headers: { 'X-Admin-Key': key } }).then((r) => r.data);
}

function adminPost<T>(path: string, key: string) {
  return client.post<T>(`/v1/admin${path}`, null, { headers: { 'X-Admin-Key': key } }).then((r) => r.data);
}

export default function AdminPage() {
  const { t, i18n } = useTranslation();
  const [key, setKey] = useState<string | null>(() => sessionStorage.getItem(KEY_STORAGE));
  const [tab, setTab] = useState<Tab>('overview');

  const [gateInput, setGateInput] = useState('');
  const [gateError, setGateError] = useState('');
  const [gateBusy, setGateBusy] = useState(false);

  const [overview, setOverview] = useState<Overview | null>(null);
  const [users, setUsers] = useState<AdminUser[] | null>(null);
  const [companies, setCompanies] = useState<AdminCompany[] | null>(null);
  const [regulations, setRegulations] = useState<AdminRegulation[] | null>(null);
  const [error, setError] = useState('');
  const [notice, setNotice] = useState('');

  const [confirm, setConfirm] = useState<Confirm>(null);
  const [confirmBusy, setConfirmBusy] = useState(false);
  const [newPassword, setNewPassword] = useState<{ email: string; password: string } | null>(null);
  const [copied, setCopied] = useState(false);

  const signOut = useCallback(() => {
    sessionStorage.removeItem(KEY_STORAGE);
    setKey(null);
  }, []);

  const loadTab = useCallback(
    (target: Tab, adminKey: string) => {
      setError('');
      const fail = (e: any) => {
        if (e?.response?.status === 401) return signOut();
        setError(e?.response?.data?.detail || t('appnew.admin.loadError'));
      };
      if (target === 'overview') adminGet<Overview>('/overview', adminKey).then(setOverview).catch(fail);
      if (target === 'users') adminGet<AdminUser[]>('/users', adminKey).then(setUsers).catch(fail);
      if (target === 'workspaces') adminGet<AdminCompany[]>('/companies', adminKey).then(setCompanies).catch(fail);
      if (target === 'regulations') adminGet<AdminRegulation[]>('/regulations', adminKey).then(setRegulations).catch(fail);
    },
    [signOut, t]
  );

  useEffect(() => {
    if (key) loadTab(tab, key);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, tab]);

  const enter = async (e: React.FormEvent) => {
    e.preventDefault();
    setGateBusy(true);
    setGateError('');
    try {
      await adminGet<Overview>('/overview', gateInput.trim());
      sessionStorage.setItem(KEY_STORAGE, gateInput.trim());
      setKey(gateInput.trim());
    } catch (err: any) {
      const status = err?.response?.status;
      setGateError(
        status === 401
          ? t('appnew.admin.gate.wrongKey')
          : status === 503
            ? t('appnew.admin.gate.notConfigured')
            : t('appnew.admin.gate.error')
      );
    } finally {
      setGateBusy(false);
    }
  };

  const fmtDate = (s: string | null) => {
    if (!s) return '';
    const d = new Date(s);
    return Number.isNaN(d.getTime())
      ? s
      : d.toLocaleDateString(i18n.language === 'zh' ? 'zh-CN' : 'en', { year: 'numeric', month: 'short', day: 'numeric' });
  };

  const toggleDisabled = (user: AdminUser) => {
    if (!key) return;
    setError('');
    setNotice('');
    adminPost<{ disabled: boolean }>(`/users/${user.id}/${user.disabled ? 'enable' : 'disable'}`, key)
      .then(() => {
        setNotice(t(user.disabled ? 'appnew.admin.users.enableDone' : 'appnew.admin.users.disableDone', { email: user.email }));
        loadTab('users', key);
      })
      .catch((e: any) => {
        if (e?.response?.status === 401) return signOut();
        setError(e?.response?.data?.detail || t('appnew.admin.loadError'));
      });
  };

  const runConfirm = () => {
    if (!key || !confirm) return;
    setConfirmBusy(true);
    setError('');
    setNotice('');
    const done = () => {
      setConfirm(null);
      setConfirmBusy(false);
    };
    const fail = (e: any) => {
      setConfirmBusy(false);
      if (e?.response?.status === 401) return signOut();
      setError(e?.response?.data?.detail || t('appnew.admin.loadError'));
    };
    if (confirm.kind === 'resetPassword') {
      adminPost<{ new_password: string }>(`/users/${confirm.user.id}/reset-password`, key)
        .then((r) => {
          done();
          setCopied(false);
          setNewPassword({ email: confirm.user.email, password: r.new_password });
        })
        .catch(fail);
    }
    if (confirm.kind === 'reseed') {
      adminPost<{ regulations: number; legal_units: number; requirements: number }>('/regulations/reseed', key)
        .then((r) => {
          done();
          setNotice(t('appnew.admin.regulations.reseedDone', { regulations: r.regulations, units: r.legal_units, requirements: r.requirements }));
          loadTab('regulations', key);
        })
        .catch(fail);
    }
    if (confirm.kind === 'demoReset') {
      adminPost<{ deleted_companies: number; deleted_products: number; deleted_sessions: number }>('/demo/reset', key)
        .then((r) => {
          done();
          setNotice(
            t('appnew.admin.regulations.demoResetDone', { companies: r.deleted_companies, products: r.deleted_products, sessions: r.deleted_sessions })
          );
          loadTab('regulations', key);
        })
        .catch(fail);
    }
  };

  const copyPassword = () => {
    if (!newPassword) return;
    navigator.clipboard?.writeText(newPassword.password).then(() => setCopied(true));
  };

  if (!key) {
    return (
      <main className="ds-admin-gate">
        <form onSubmit={enter}>
          <Link to="/" className="ds-brand">
            <span className="ds-logo">D</span>
            <span>DataShield</span>
          </Link>
          <h1>{t('appnew.admin.gate.title')}</h1>
          <p>{t('appnew.admin.gate.subtitle')}</p>
          <label>
            {t('appnew.admin.gate.label')}
            <input
              type="password"
              required
              value={gateInput}
              onChange={(e) => setGateInput(e.target.value)}
              placeholder={t('appnew.admin.gate.placeholder')}
              autoComplete="off"
            />
          </label>
          {gateError && <div className="ds-inline-error" role="alert">{gateError}</div>}
          <button className="ds-button primary" type="submit" disabled={gateBusy}>
            {gateBusy ? t('appnew.admin.gate.verifying') : t('appnew.admin.gate.submit')}
          </button>
          <Link to="/" className="ds-admin-gate-home">{t('appnew.admin.backHome')}</Link>
        </form>
      </main>
    );
  }

  const tabs: { id: Tab; label: string }[] = [
    { id: 'overview', label: t('appnew.admin.tabs.overview') },
    { id: 'users', label: t('appnew.admin.tabs.users') },
    { id: 'workspaces', label: t('appnew.admin.tabs.workspaces') },
    { id: 'regulations', label: t('appnew.admin.tabs.regulations') },
  ];

  const overviewCards: { label: string; value: number }[] = overview
    ? [
        { label: t('appnew.admin.overview.users'), value: overview.users },
        { label: t('appnew.admin.overview.companies'), value: overview.companies },
        { label: t('appnew.admin.overview.products'), value: overview.products },
        { label: t('appnew.admin.overview.analysisRuns'), value: overview.analysis_runs },
        { label: t('appnew.admin.overview.tenantRuns'), value: overview.tenant_agent_runs },
        { label: t('appnew.admin.overview.findings'), value: overview.findings },
        { label: t('appnew.admin.overview.regulations'), value: overview.regulations },
        { label: t('appnew.admin.overview.legalUnits'), value: overview.legal_units },
        { label: t('appnew.admin.overview.activeSessions'), value: overview.active_sessions },
      ]
    : [];

  return (
    <main className="ds-admin">
      <nav className="ds-admin-nav">
        <Link to="/" className="ds-brand">
          <span className="ds-logo">D</span>
          <span>DataShield</span>
        </Link>
        <div className="ds-admin-nav-actions">
          <LanguageSwitcher />
          <button className="ds-button quiet" onClick={signOut}>{t('appnew.admin.signOut')}</button>
        </div>
      </nav>
      <div className="ds-admin-body">
        <header>
          <span className="ds-eyebrow">{t('appnew.admin.eyebrow')}</span>
          <h1>{t('appnew.admin.title')}</h1>
          <p>{t('appnew.admin.subtitle')}</p>
        </header>
        <div className="ds-admin-tabs" role="tablist">
          {tabs.map((item) => (
            <button key={item.id} role="tab" aria-selected={tab === item.id} className={tab === item.id ? 'active' : ''} onClick={() => setTab(item.id)}>
              {item.label}
            </button>
          ))}
        </div>
        {notice && <div className="ds-admin-notice" role="status">{notice}</div>}
        {error && (
          <div className="ds-inline-error" role="alert">
            {error} <button onClick={() => key && loadTab(tab, key)}>{t('appnew.admin.retry')}</button>
          </div>
        )}

        {tab === 'overview' &&
          (overview ? (
            <div className="ds-admin-cards">
              {overviewCards.map((card) => (
                <div className="ds-admin-card" key={card.label}>
                  <span>{card.label}</span>
                  <strong>{card.value}</strong>
                </div>
              ))}
            </div>
          ) : (
            !error && <Spinner text={t('appnew.admin.loading')} />
          ))}

        {tab === 'users' &&
          (users ? (
            users.length === 0 ? (
              <p>{t('appnew.admin.users.empty')}</p>
            ) : (
              <table className="ds-admin-table">
                <thead>
                  <tr>
                    <th>{t('appnew.admin.users.email')}</th>
                    <th>{t('appnew.admin.users.name')}</th>
                    <th>{t('appnew.admin.users.company')}</th>
                    <th>{t('appnew.admin.users.edition')}</th>
                    <th>{t('appnew.admin.users.status')}</th>
                    <th>{t('appnew.admin.users.createdAt')}</th>
                    <th>{t('appnew.admin.users.lastLogin')}</th>
                    <th>{t('appnew.admin.users.sessions')}</th>
                    <th>{t('appnew.admin.users.actions')}</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((u) => (
                    <tr key={u.id}>
                      <td>
                        {u.email}
                        <small>{u.email_verified ? t('appnew.admin.users.verified') : t('appnew.admin.users.unverified')}</small>
                      </td>
                      <td>{u.display_name}</td>
                      <td>{u.company_name}</td>
                      <td>{u.edition}</td>
                      <td>
                        <span className={`ds-admin-status${u.disabled ? ' off' : ''}`}>
                          {u.disabled ? t('appnew.admin.users.disabled') : t('appnew.admin.users.active')}
                        </span>
                      </td>
                      <td>{fmtDate(u.created_at)}</td>
                      <td>{u.last_login_at ? fmtDate(u.last_login_at) : t('appnew.admin.users.never')}</td>
                      <td>{u.active_sessions}</td>
                      <td>
                        <div className="ds-admin-actions">
                          <button className={u.disabled ? '' : 'danger'} onClick={() => toggleDisabled(u)}>
                            {u.disabled ? t('appnew.admin.users.enable') : t('appnew.admin.users.disable')}
                          </button>
                          <button onClick={() => setConfirm({ kind: 'resetPassword', user: u })}>{t('appnew.admin.users.resetPassword')}</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          ) : (
            !error && <Spinner text={t('appnew.admin.loading')} />
          ))}

        {tab === 'workspaces' &&
          (companies ? (
            companies.length === 0 ? (
              <p>{t('appnew.admin.workspaces.empty')}</p>
            ) : (
              <table className="ds-admin-table">
                <thead>
                  <tr>
                    <th>{t('appnew.admin.workspaces.name')}</th>
                    <th>{t('appnew.admin.workspaces.type')}</th>
                    <th>{t('appnew.admin.workspaces.products')}</th>
                    <th>{t('appnew.admin.workspaces.members')}</th>
                    <th>{t('appnew.admin.workspaces.createdAt')}</th>
                  </tr>
                </thead>
                <tbody>
                  {companies.map((c) => (
                    <tr key={c.id}>
                      <td>{c.name}</td>
                      <td>{c.business_model}</td>
                      <td>{c.products}</td>
                      <td>
                        {(c.users||[]).length === 0
                          ? t('appnew.admin.workspaces.noMembers')
                          : (c.users||[]).map((email) => <small key={email}>{email}</small>)}
                      </td>
                      <td>{fmtDate(c.created_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )
          ) : (
            !error && <Spinner text={t('appnew.admin.loading')} />
          ))}

        {tab === 'regulations' &&
          (regulations ? (
            <>
              {regulations.length === 0 ? (
                <p>{t('appnew.admin.regulations.empty')}</p>
              ) : (
                <table className="ds-admin-table">
                  <thead>
                    <tr>
                      <th>{t('appnew.admin.regulations.name')}</th>
                      <th>{t('appnew.admin.regulations.shortName')}</th>
                      <th>{t('appnew.admin.regulations.identifier')}</th>
                      <th>{t('appnew.admin.regulations.jurisdiction')}</th>
                      <th>{t('appnew.admin.regulations.status')}</th>
                      <th>{t('appnew.admin.regulations.versions')}</th>
                      <th>{t('appnew.admin.regulations.legalUnits')}</th>
                      <th>{t('appnew.admin.regulations.requirements')}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {regulations.map((r) => (
                      <tr key={r.id}>
                        <td>{r.name}</td>
                        <td>{r.short_name}</td>
                        <td>{r.official_identifier}</td>
                        <td>{r.jurisdiction}</td>
                        <td>{r.status}</td>
                        <td>{r.versions}</td>
                        <td>{r.legal_units}</td>
                        <td>{r.requirements}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )}
              <section className="ds-admin-danger">
                <h2>{t('appnew.admin.regulations.dangerTitle')}</h2>
                <p>{t('appnew.admin.regulations.dangerSubtitle')}</p>
                <div className="ds-button-row">
                  <button onClick={() => setConfirm({ kind: 'reseed' })}>{t('appnew.admin.regulations.reseed')}</button>
                  <button onClick={() => setConfirm({ kind: 'demoReset' })}>{t('appnew.admin.regulations.demoReset')}</button>
                </div>
              </section>
            </>
          ) : (
            !error && <Spinner text={t('appnew.admin.loading')} />
          ))}
      </div>

      {confirm && (
        <div className="ds-admin-modal" role="dialog" aria-modal="true">
          <div className="ds-admin-dialog">
            <h2>
              {confirm.kind === 'resetPassword' && t('appnew.admin.reset.confirmTitle')}
              {confirm.kind === 'reseed' && t('appnew.admin.regulations.reseedTitle')}
              {confirm.kind === 'demoReset' && t('appnew.admin.regulations.demoResetTitle')}
            </h2>
            <p>
              {confirm.kind === 'resetPassword' && t('appnew.admin.reset.confirmBody', { email: confirm.user.email })}
              {confirm.kind === 'reseed' && t('appnew.admin.regulations.reseedBody')}
              {confirm.kind === 'demoReset' && t('appnew.admin.regulations.demoResetBody')}
            </p>
            <div className="ds-admin-dialog-actions">
              <button disabled={confirmBusy} onClick={() => setConfirm(null)}>
                {confirm.kind === 'resetPassword' ? t('appnew.admin.reset.cancel') : t('appnew.admin.regulations.cancel')}
              </button>
              <button className={confirm.kind === 'resetPassword' ? 'primary' : 'danger'} disabled={confirmBusy} onClick={runConfirm}>
                {confirmBusy
                  ? confirm.kind === 'reseed'
                    ? t('appnew.admin.regulations.reseedRunning')
                    : confirm.kind === 'demoReset'
                      ? t('appnew.admin.regulations.demoResetRunning')
                      : t('appnew.admin.reset.confirm')
                  : confirm.kind === 'resetPassword'
                    ? t('appnew.admin.reset.confirm')
                    : t('appnew.admin.regulations.confirm')}
              </button>
            </div>
          </div>
        </div>
      )}

      {newPassword && (
        <div className="ds-admin-modal" role="dialog" aria-modal="true">
          <div className="ds-admin-dialog">
            <h2>{t('appnew.admin.reset.resultTitle')}</h2>
            <p>{t('appnew.admin.reset.resultBody')}</p>
            <div className="ds-admin-password">
              <span>{newPassword.password}</span>
            </div>
            <div className="ds-admin-dialog-actions">
              <button onClick={copyPassword}>{copied ? t('appnew.admin.reset.copied') : t('appnew.admin.reset.copy')}</button>
              <button className="primary" onClick={() => setNewPassword(null)}>{t('appnew.admin.reset.close')}</button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}
