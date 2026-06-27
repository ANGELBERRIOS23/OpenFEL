import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard, Key, Users, FileText, Search, Activity,
  ScrollText, LogOut, Sun, Moon, Book, Menu, X, Terminal,
} from 'lucide-react';
import { clearKey } from '../lib/api';
import { getTheme, toggleTheme } from '../lib/theme';
import { useState } from 'react';

const links = [
  { to: '/', icon: LayoutDashboard, label: 'Dashboard' },
  { to: '/accounts', icon: Users, label: 'Cuentas' },
  { to: '/keys', icon: Key, label: 'API Keys' },
  { to: '/emit', icon: FileText, label: 'Emitir' },
  { to: '/query', icon: Search, label: 'Consultar' },
  { to: '/health', icon: Activity, label: 'Health' },
  { to: '/logs', icon: ScrollText, label: 'Logs' },
  { to: '/docs', icon: Book, label: 'Docs' },
  { to: '/playground', icon: Terminal, label: 'Playground' },
];

export default function Layout() {
  const [theme, setThemeState] = useState(getTheme());
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const isDark = theme === 'dark';

  const bg = isDark ? 'bg-[#1e293b]' : 'bg-white';
  const border = isDark ? 'border-slate-700' : 'border-slate-200';
  const text = isDark ? 'text-slate-300' : 'text-slate-600';
  const textH = isDark ? 'text-white' : 'text-slate-900';
  const hoverBg = isDark ? 'hover:bg-slate-700/50' : 'hover:bg-slate-100';
  const mainBg = isDark ? 'bg-[#0f172a]' : 'bg-slate-50';

  function handleToggle() {
    const next = toggleTheme();
    setThemeState(next);
  }

  return (
    <div className="flex min-h-screen">
      {/* Mobile hamburger */}
      <button
        onClick={() => setSidebarOpen(!sidebarOpen)}
        className={`md:hidden fixed top-3 left-3 z-50 p-2 rounded-lg ${bg} ${border} border cursor-pointer`}
      >
        {sidebarOpen ? <X size={20} className={textH} /> : <Menu size={20} className={textH} />}
      </button>

      {/* Overlay */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 bg-black/50 z-30" onClick={() => setSidebarOpen(false)} />
      )}

      {/* Sidebar */}
      <aside className={`${bg} border-r ${border} flex flex-col w-56 shrink-0
        fixed md:static inset-y-0 left-0 z-40 transform transition-transform duration-200
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full md:translate-x-0'}`}
      >
        <div className={`p-4 border-b ${border}`}>
          <h1 className={`text-xl font-bold ${textH} tracking-tight`}>OpenFEL</h1>
          <p className={`text-xs ${text} mt-1`}>SAT Guatemala</p>
        </div>
        <nav className="flex-1 p-2 space-y-1">
          {links.map(({ to, icon: Icon, label }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setSidebarOpen(false)}
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                  isActive
                    ? 'bg-accent/20 text-accent'
                    : `${text} ${hoverBg} hover:${textH}`
                }`
              }
            >
              <Icon size={18} />
              {label}
            </NavLink>
          ))}
        </nav>
        <div className={`border-t ${border} p-2 space-y-1`}>
          <button
            onClick={handleToggle}
            className={`flex items-center gap-3 px-3 py-2 w-full text-sm ${text} ${hoverBg} rounded-lg cursor-pointer`}
          >
            {isDark ? <Sun size={18} /> : <Moon size={18} />}
            {isDark ? 'Modo claro' : 'Modo oscuro'}
          </button>
          <button
            onClick={() => { clearKey(); window.location.href = '/login'; }}
            className={`flex items-center gap-3 px-3 py-2 w-full text-sm ${text} hover:text-red-400 rounded-lg cursor-pointer`}
          >
            <LogOut size={18} />
            Salir
          </button>
        </div>
      </aside>
      <main className={`flex-1 p-4 md:p-6 overflow-auto ${mainBg} ${sidebarOpen ? '' : 'ml-0'} pt-14 md:pt-6`}>
        <Outlet context={{ isDark }} />
      </main>
    </div>
  );
}
