import { NavLink, Outlet } from 'react-router-dom';
import {
  LayoutDashboard,
  Network,
  Truck,
  ArrowLeftRight,
  PlusSquare,
  BarChart3,
  TrendingUp,
  AlertTriangle,
  Bell,
  History,
  FileText,
  Settings,
  RefreshCw,
  Menu,
  X,
} from 'lucide-react';
import { useState } from 'react';
import { useData } from '../hooks/useData';
import clsx from 'clsx';

const NAV = [
  { to: '/', label: 'Command Center', icon: LayoutDashboard },
  { to: '/architecture', label: 'Architecture', icon: Network },
  { to: '/assets', label: 'Live Fleet', icon: Truck },
  { to: '/add-data', label: 'Add Data', icon: PlusSquare },
  { to: '/check-in-out', label: 'Dispatch / Return', icon: ArrowLeftRight },
  { to: '/analytics', label: 'Usage Lake', icon: BarChart3 },
  { to: '/forecast', label: 'Demand ML', icon: TrendingUp },
  { to: '/anomalies', label: 'Misuse Engine', icon: AlertTriangle },
  { to: '/notifications', label: 'SNS Alerts', icon: Bell },
  { to: '/rentals', label: 'Contracts', icon: History },
  { to: '/reports', label: 'Reports', icon: FileText },
  { to: '/settings', label: 'Settings', icon: Settings },
];

export function AppLayout() {
  const { lastUpdated, dataSource, warnings, refreshing, refresh, unreadCount } = useData();
  const [open, setOpen] = useState(false);

  return (
    <div className="flex min-h-full bg-cat-light">
      <aside
        className={clsx(
          'fixed inset-y-0 left-0 z-40 flex w-56 flex-col bg-cat-black text-white transition-transform lg:static lg:translate-x-0',
          open ? 'translate-x-0' : '-translate-x-full',
        )}
      >
        <div className="px-5 pb-4 pt-6">
          <div className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center bg-cat-yellow text-sm font-bold text-cat-black">
              SR
            </span>
            <div>
              <p className="text-[13px] font-bold leading-tight tracking-wide">Smart Rental</p>
              <p className="text-[10px] uppercase tracking-[0.18em] text-white/45">Hybrid Cloud</p>
            </div>
          </div>
        </div>

        <nav className="flex-1 space-y-0.5 overflow-y-auto px-2 pb-4">
          {NAV.map(({ to, label, icon: Icon }) => (
            <NavLink
              key={to}
              to={to}
              end={to === '/'}
              onClick={() => setOpen(false)}
              className={({ isActive }) =>
                clsx(
                  'flex items-center gap-3 px-3 py-2 text-[13px] font-medium transition-colors',
                  isActive
                    ? 'bg-cat-yellow text-cat-black'
                    : 'text-white/70 hover:bg-white/5 hover:text-white',
                )
              }
            >
              <Icon size={15} strokeWidth={2} />
              <span className="flex-1">{label}</span>
              {label === 'SNS Alerts' && unreadCount > 0 && (
                <span className="bg-cat-yellow px-1.5 text-[10px] font-bold text-cat-black">
                  {unreadCount}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
      </aside>

      {open && (
        <button
          type="button"
          className="fixed inset-0 z-30 bg-black/40 lg:hidden"
          aria-label="Close menu"
          onClick={() => setOpen(false)}
        />
      )}

      <div className="flex min-w-0 flex-1 flex-col">
        <header className="sticky top-0 z-20 flex h-14 items-center gap-4 border-b border-cat-muted bg-cat-light/95 px-4 backdrop-blur lg:px-8">
          <button
            type="button"
            className="lg:hidden"
            onClick={() => setOpen(true)}
            aria-label="Open menu"
          >
            {open ? <X size={20} /> : <Menu size={20} />}
          </button>

          <div className="min-w-0 flex-1">
            <p className="truncate text-sm font-semibold text-cat-black">Hybrid-Cloud Fleet Ops</p>
          </div>

          <div className="hidden items-center gap-4 text-[11px] text-cat-gray md:flex">
            <span>
              Source <strong className="font-semibold text-cat-black">{dataSource}</strong>
            </span>
            <span className="h-3 w-px bg-cat-muted" />
            <span>
              Updated{' '}
              <strong className="font-semibold text-cat-black">
                {lastUpdated ? new Date(lastUpdated).toLocaleTimeString() : '—'}
              </strong>
            </span>
          </div>

          <NavLink
            to="/notifications"
            className="relative p-1.5 text-cat-gray hover:text-cat-black"
            aria-label="Notifications"
          >
            <Bell size={17} />
            {unreadCount > 0 && <span className="absolute right-1 top-1 h-1.5 w-1.5 bg-cat-yellow" />}
          </NavLink>

          <button
            type="button"
            onClick={() => refresh(false)}
            disabled={refreshing}
            className="btn-primary"
          >
            <RefreshCw size={13} className={refreshing ? 'animate-spin' : ''} />
            Refresh
          </button>
        </header>

        {warnings.length > 0 && (
          <div className="bg-amber-50 px-4 py-2 text-xs text-amber-900 lg:px-8">
            Data notice: {warnings[0]}
            {warnings.length > 1 && ` (+${warnings.length - 1} more)`}
          </div>
        )}

        <main className="flex-1 overflow-auto px-4 py-6 lg:px-8 lg:py-8">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
