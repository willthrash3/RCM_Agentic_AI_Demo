import { NavLink, Outlet } from 'react-router-dom';
import clsx from 'clsx';

const NAV = [
  { to: '/dashboard', label: 'Dashboard' },
  { to: '/claims', label: 'Claims' },
  { to: '/patients', label: 'Patients' },
  { to: '/review-queue', label: 'Review Queue' },
  { to: '/denials', label: 'Denials' },
  { to: '/agent-trace', label: 'Agent Trace' },
  { to: '/analytics', label: 'Analytics' },
  { to: '/scenarios', label: 'Scenarios' },
];

export default function Layout() {
  return (
    <div className="flex h-screen">
      <aside className="w-56 bg-ink text-white flex flex-col">
        <div className="px-4 py-5 border-b border-slate-700">
          <div className="text-lg font-semibold">RCM Agentic AI</div>
          <div className="text-xs text-slate-400">Demo v1.0</div>
        </div>
        <nav className="flex-1 p-2">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                clsx(
                  'block px-3 py-2 rounded text-sm my-0.5 transition-colors',
                  isActive
                    ? 'bg-envblue text-white'
                    : 'text-slate-300 hover:bg-slate-800',
                )
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-3 text-xs text-slate-500 border-t border-slate-800">
          Synthetic data · No real PHI
        </div>
      </aside>
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
