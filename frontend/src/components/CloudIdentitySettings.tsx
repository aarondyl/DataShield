import { useEffect, useState } from 'react';
import { invoke } from '@tauri-apps/api/core';
import { useTranslation } from 'react-i18next';
import client from '../api/client';
import { identityErrorMessage } from '../features/auth/identityErrors';

type IdentityView = { userId?: number; email: string; name?: string; organization?: { id: number; name: string; edition: string; role: string } };
type Organization = { id: number; name: string; edition: string; role: string; active: boolean };
type Member = { user_id: number; email: string; name: string; role: string };
type DeviceSession = { id: number; device_name: string; created_at: string; last_used_at: string; current: boolean };

export default function CloudIdentitySettings() {
  const { t } = useTranslation();
  const [baseUrl, setBaseUrl] = useState('');
  const [account, setAccount] = useState<IdentityView | null>(null);
  const [status, setStatus] = useState<'checking' | 'signed-in' | 'signed-out' | 'unavailable'>('checking');
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState('');
  const [organizations, setOrganizations] = useState<Organization[]>([]);
  const [members, setMembers] = useState<Member[]>([]);
  const [inviteEmail, setInviteEmail] = useState('');
  const [inviteCode, setInviteCode] = useState('');
  const [sessions, setSessions] = useState<DeviceSession[]>([]);

  const load = async () => {
    try {
      const { data } = await client.get<{ base_url: string }>('/v1/local-regulations/configuration');
      const endpoint = data.base_url ? `${data.base_url.replace(/\/$/, '')}/identity` : '';
      setBaseUrl(endpoint);
      if (!endpoint) { setStatus('unavailable'); return; }
      const value = await invoke<IdentityView>('cloud_identity_me', { input: { baseUrl: endpoint } });
      setAccount(value); setStatus('signed-in');
      setSessions(await invoke<DeviceSession[]>('cloud_identity_sessions', { input: { baseUrl: endpoint } }));
      const orgs = await invoke<Organization[]>('cloud_identity_organizations', { input: { baseUrl: endpoint } });
      setOrganizations(orgs);
      if (value.organization?.id) setMembers(await invoke<Member[]>('cloud_identity_members', { input: { baseUrl: endpoint, organizationId: value.organization.id } }));
    } catch (error) {
      setAccount(null);
      setStatus(String(error).includes('IDENTITY_SESSION_MISSING') ? 'signed-out' : 'unavailable');
    }
  };

  const switchOrganization = async (organizationId: number) => {
    setBusy(true); setMessage('');
    try {
      const value = await invoke<IdentityView>('cloud_identity_switch_organization', { input: { baseUrl, organizationId } });
      setAccount(value); await load(); setMessage(t('appnew.desktopAccount.organizationSwitched'));
    } catch (error) { setMessage(identityErrorMessage(error, t)); }
    finally { setBusy(false); }
  };

  const invite = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setMessage('');
    try {
      const organizationId = account?.organization?.id;
      if (!organizationId) return;
      await invoke('cloud_identity_invite', { input: { baseUrl, organizationId, email: inviteEmail, role: 'member' } });
      setInviteEmail(''); setMessage(t('appnew.desktopAccount.invitationSent'));
    } catch (error) { setMessage(identityErrorMessage(error, t)); }
    finally { setBusy(false); }
  };

  const acceptInvitation = async (event: React.FormEvent) => {
    event.preventDefault(); setBusy(true); setMessage('');
    try {
      await invoke('cloud_identity_accept_invitation', { input: { baseUrl, code: inviteCode } });
      setInviteCode(''); await load(); setMessage(t('appnew.desktopAccount.invitationAccepted'));
    } catch (error) { setMessage(identityErrorMessage(error, t)); }
    finally { setBusy(false); }
  };

  const changeRole = async (member: Member, role: 'admin' | 'member') => {
    const organizationId = account?.organization?.id;
    if (!organizationId) return;
    setBusy(true); setMessage('');
    try {
      await invoke('cloud_identity_change_member_role', { input: { baseUrl, organizationId, userId: member.user_id, role } });
      await load(); setMessage(t('appnew.desktopAccount.roleUpdated'));
    } catch (error) { setMessage(identityErrorMessage(error, t)); }
    finally { setBusy(false); }
  };

  const removeMember = async (member: Member) => {
    const organizationId = account?.organization?.id;
    if (!organizationId || !window.confirm(t('appnew.desktopAccount.confirmRemoveMember', { email: member.email }))) return;
    setBusy(true); setMessage('');
    try {
      await invoke('cloud_identity_remove_member', { input: { baseUrl, organizationId, userId: member.user_id } });
      await load(); setMessage(t('appnew.desktopAccount.memberRemoved'));
    } catch (error) { setMessage(identityErrorMessage(error, t)); }
    finally { setBusy(false); }
  };

  const revokeSession = async (sessionId: number) => {
    setBusy(true); setMessage('');
    try {
      await invoke('cloud_identity_revoke_session', { input: { baseUrl, sessionId } });
      setSessions(await invoke<DeviceSession[]>('cloud_identity_sessions', { input: { baseUrl } }));
      setMessage(t('appnew.desktopAccount.sessionRevoked'));
    } catch (error) { setMessage(identityErrorMessage(error, t)); }
    finally { setBusy(false); }
  };
  useEffect(() => { void load(); }, []);

  const signOut = async () => {
    setBusy(true); setMessage('');
    try { await invoke('cloud_identity_logout', { input: { baseUrl } }); setAccount(null); setStatus('signed-out'); setMessage(t('appnew.desktopAccount.signedOut')); }
    catch { setAccount(null); setStatus('signed-out'); setMessage(t('appnew.desktopAccount.localSignedOutRemoteMayExpire')); }
    finally { setBusy(false); }
  };

  return <section className="ds-action-block"><h2>{t('appnew.desktopAccount.accountSettings')}</h2><div>
    <p>{account ? t('appnew.desktopAccount.signedIn', { email: account.email, organization: account.organization?.name || '' }) : status === 'unavailable' ? t('appnew.desktopAccount.statusUnavailable') : status === 'checking' ? t('appnew.desktopAccount.checking') : t('appnew.desktopAccount.signedOutState')}</p>
    {account?.organization && <>
      {organizations.length > 1 && <label>{t('appnew.desktopAccount.activeOrganization')}<select value={account.organization.id} disabled={busy} onChange={event => void switchOrganization(Number(event.target.value))}>{organizations.map(org => <option key={org.id} value={org.id}>{org.name}</option>)}</select></label>}
      <ul>{members.map(member => <li key={member.user_id}>
        {member.name} · {member.email} · {t(`appnew.desktopAccount.roles.${member.role}`, { defaultValue: member.role })}
        {account.organization?.role === 'owner' && member.role !== 'owner' && <select aria-label={t('appnew.desktopAccount.memberRole')} value={member.role} disabled={busy} onChange={event => void changeRole(member, event.target.value as 'admin' | 'member')}><option value="member">{t('appnew.desktopAccount.roles.member')}</option><option value="admin">{t('appnew.desktopAccount.roles.admin')}</option></select>}
        {['owner', 'admin'].includes(account.organization?.role || '') && member.role !== 'owner' && member.user_id !== account.userId && !(account.organization?.role === 'admin' && member.role === 'admin') && <button className="ds-button quiet" disabled={busy} onClick={() => void removeMember(member)}>{t('appnew.desktopAccount.removeMember')}</button>}
      </li>)}</ul>
      {['owner', 'admin'].includes(account.organization.role) && <form onSubmit={invite}><label>{t('appnew.desktopAccount.inviteMember')}<input type="email" required maxLength={320} value={inviteEmail} onChange={event => setInviteEmail(event.target.value)} /></label><button className="ds-button quiet" disabled={busy}>{t('appnew.desktopAccount.sendInvitation')}</button></form>}
      <form onSubmit={acceptInvitation}><label>{t('appnew.desktopAccount.invitationCode')}<input required maxLength={256} value={inviteCode} onChange={event => setInviteCode(event.target.value)} /></label><button className="ds-button quiet" disabled={busy}>{t('appnew.desktopAccount.acceptInvitation')}</button></form>
    </>}
    {account && <button className="ds-button quiet" disabled={busy} onClick={signOut}>{busy ? t('appnew.settings.signingOut') : t('appnew.settings.logOut')}</button>}
    {account && <><h3>{t('appnew.desktopAccount.deviceSessions')}</h3><ul>{sessions.map(item => <li key={item.id}>{item.device_name} · {new Date(item.last_used_at).toLocaleString()} · {item.current ? t('appnew.desktopAccount.currentSession') : <button className="ds-button quiet" disabled={busy} onClick={() => void revokeSession(item.id)}>{t('appnew.desktopAccount.revokeSession')}</button>}</li>)}</ul></>}
    {message && <p role="status" className="ds-cloud-notice">{message}</p>}
  </div></section>;
}
