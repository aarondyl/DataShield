import { NavLink, Outlet } from 'react-router-dom';

const nav = [
  { to: '/app/today', label: 'Today', icon: 'sun' },
  { to: '/app/monitor', label: 'Monitor', icon: 'pulse' },
  { to: '/app/findings', label: 'Findings', icon: 'finding' },
  { to: '/app/actions', label: 'Actions', icon: 'check' },
  { to: '/app/product', label: 'Product', icon: 'cube' },
];

function Icon({ name }: { name: string }) {
  const paths: Record<string, React.ReactNode> = {
    sun: <><circle cx="12" cy="12" r="3.5"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></>,
    pulse: <path d="M3 12h4l2-5 4 10 2-5h6"/>,
    finding: <><circle cx="11" cy="11" r="7"/><path d="m16 16 5 5M11 8v4M11 15h.01"/></>,
    check: <><rect x="3" y="3" width="18" height="18" rx="4"/><path d="m8 12 2.5 2.5L16 9"/></>,
    cube: <><path d="m12 2 9 5-9 5-9-5 9-5Z"/><path d="m3 7 9 5 9-5M12 12v10M3 7v10l9 5 9-5V7"/></>,
  };
  return <svg viewBox="0 0 24 24" aria-hidden="true">{paths[name]}</svg>;
}

export default function AppShell() {
  return <div className="ds-shell">
    <aside className="ds-sidebar">
      <NavLink to="/app/today" className="ds-brand"><span className="ds-logo">D</span><span>DataShield</span></NavLink>
      <div className="ds-workspace"><span>Workspace</span><strong>My product</strong><small>Developer edition</small></div>
      <nav aria-label="Primary navigation">{nav.map(item => <NavLink key={item.to} to={item.to} className={({isActive}) => `ds-nav-link${isActive ? ' active' : ''}`}><Icon name={item.icon}/><span>{item.label}</span></NavLink>)}</nav>
      <div className="ds-sidebar-bottom">
        <NavLink to="/app/settings" className="ds-nav-link"><Icon name="cube"/><span>Settings</span></NavLink>
        <div className="ds-profile"><span>A</span><div><strong>Aaron</strong><small>Local workspace</small></div></div>
      </div>
    </aside>
    <main className="ds-main"><Outlet/></main>
  </div>;
}
