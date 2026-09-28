import { NavLink, Outlet } from 'react-router-dom';

const navItems = [
  { to: '/', label: '总览', end: true },
  { to: '/company', label: '企业档案' },
  { to: '/products', label: '产品管理' },
  { to: '/assessment', label: '合规自查' },
  { to: '/analyze', label: '法规影响分析' },
  { to: '/privacy', label: '隐私政策工具' },
  { to: '/regulations', label: '法规库' },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen bg-gray-50">
      <aside className="w-56 shrink-0 bg-slate-900 text-slate-200 flex flex-col">
        <div className="px-5 py-5 border-b border-slate-700">
          <div className="text-lg font-semibold text-white">DataShield</div>
          <div className="text-xs text-slate-400 mt-1">智能数据合规平台</div>
        </div>
        <nav className="flex-1 py-3">
          {navItems.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                `block px-5 py-2.5 text-sm border-l-2 ${
                  isActive
                    ? 'border-indigo-500 bg-slate-800 text-white'
                    : 'border-transparent text-slate-300 hover:bg-slate-800 hover:text-white'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
      </aside>
      <main className="flex-1 p-8 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
