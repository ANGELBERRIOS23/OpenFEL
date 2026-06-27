import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard, Key, Users, FileText, Search, Activity,
  ScrollText, LogOut,
} from 'lucide-react';
import { clearKey } from '../lib/api';

const links = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/accounts', icon: Users, label: 'Cuentas' },
  { to: '/keys', icon: Key, label: 'API Keys' },
  { to: '/emit', icon: FileText, label: 'Emitir' },
  { to: '/query', icon: Search, label: 'Consultar' },
  { to: '/health', icon: Activity, label: 'Health' },
  { to: '/logs', icon: ScrollText, label: 'Logs' },
];

export default function Layout() {
  return (
    <div className="flex min-h-screen">
      <aside className="w-56 bg-bg-secondary border-r border-slate-700 flex flex-col">
        <div className="p-4 border-b border-slate-700">
          <h1 className="text-xl font-bold text-white tracking-tight">OpenFEL</h1>
          <p className="text-xs text-slate-400 mt-1">SAT Guatemala</p>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {links.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-accent/20 text-accent'
                    : 'text-slate-300 hover:bg-slate-700/50 hover:text-white'
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <button
          onClick={() => { clearKey(); window.location.href = '/login'; }}
          className="flex items-center gap-3 px-5 py-3 text-sm text-slate-400 hover:text-red-400 border-t border-slate-700 cursor-pointer"
        >
          <LogOut size={18} />
          Salir
        </button>
      </aside>
      <main className="flex-1 p-6 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
