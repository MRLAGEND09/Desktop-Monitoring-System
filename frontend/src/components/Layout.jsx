import { createElement } from 'react';
import { Link, Outlet, useLocation } from 'react-router-dom';
import { useAuthStore } from '../store/auth';
import { Monitor, Bell, FileText, LogOut, User, Users, Link2 } from 'lucide-react';
import AlertToast from './AlertToast';
import { useAlertBadge } from '../hooks/useAlertBadge';

export default function Layout() {
  const logout     = useAuthStore((s) => s.logout);
  const user       = useAuthStore((s) => s.user);
  const isAdmin    = user?.role === 'admin';
  const { pathname } = useLocation();
  const alertBadge = useAlertBadge();

  const NAV = [
    { to: '/',          label: 'Dashboard', Icon: Monitor  },
    { to: '/alerts',    label: 'Alerts',    Icon: Bell,    badge: alertBadge },
    { to: '/logs',      label: 'Logs',      Icon: FileText },
    ...(isAdmin ? [
      { to: '/users',    label: 'Users',    Icon: Users   },
      { to: '/webhooks', label: 'Webhooks', Icon: Link2  },
    ] : []),
  ];

  return (
    <div className="flex h-screen overflow-hidden">
      <AlertToast />
      <aside className="w-56 flex-shrink-0 bg-gray-900 border-r border-gray-800 flex flex-col">
        <div className="px-5 py-5 border-b border-gray-800 flex flex-col items-center">
          <img src="/remote-monitoring.png" alt="Logo" className="w-10 h-10 mb-2 rounded" />
          <span className="text-lg font-bold text-white">RDM</span>
          <span className="text-xs text-gray-500 block">Remote Desktop Monitor</span>
        </div>

        <nav className="flex-1 px-3 py-4 space-y-1">
          {NAV.map(({ to, label, badge, Icon: NavIcon }) => {
            const active = to === '/' ? pathname === '/' : pathname.startsWith(to);
            return (
              <Link key={to} to={to}
                className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors
                  ${active ? 'bg-blue-700 text-white' : 'text-gray-400 hover:text-white hover:bg-gray-800'}`}>
                {createElement(NavIcon, { className: 'w-4 h-4' })}
                <span className="flex-1">{label}</span>
                {badge != null && (
                  <span className="text-xs font-bold bg-red-600 text-white rounded-full px-1.5 py-0.5 min-w-[1.25rem] text-center">
                    {badge > 99 ? '99+' : badge}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>

        <div className="px-4 py-4 border-t border-gray-800">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-8 h-8 bg-blue-700 rounded-full flex items-center justify-center">
              <User className="w-4 h-4 text-white" />
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-sm font-medium text-white truncate">{user?.username}</p>
              <p className="text-xs text-gray-500 capitalize">{user?.role}</p>
            </div>
          </div>
          <button onClick={logout}
            className="w-full flex items-center gap-2 px-3 py-2 rounded-lg text-sm text-gray-400
                       hover:text-white hover:bg-gray-800 transition-colors">
            <LogOut className="w-4 h-4" />Sign out
          </button>
        </div>
      </aside>

      <main className="flex-1 overflow-y-auto bg-gray-950">
        <Outlet />
      </main>
    </div>
  );
}
