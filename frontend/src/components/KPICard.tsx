import clsx from 'clsx';

interface KPICardProps {
  label: string;
  value: string | number;
  hint?: string;
  accent?: 'default' | 'yellow' | 'danger' | 'warning' | 'success';
  icon?: React.ReactNode;
}

export function KPICard({ label, value, accent = 'default' }: KPICardProps) {
  return (
    <div className="min-w-0 py-1">
      <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-cat-gray">{label}</p>
      <p
        className={clsx(
          'mt-1 text-[26px] font-semibold leading-none tabular-nums tracking-tight',
          accent === 'danger' && 'text-red-700',
          accent === 'warning' && 'text-amber-700',
          accent === 'success' && 'text-emerald-700',
          accent === 'yellow' && 'text-cat-black',
          accent === 'default' && 'text-cat-black',
        )}
      >
        {value}
      </p>
    </div>
  );
}

export function KPIStrip({ children }: { children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-2 gap-x-8 gap-y-5 border-y border-cat-muted bg-white px-5 py-5 sm:grid-cols-3 lg:grid-cols-6">
      {children}
    </div>
  );
}

export function MetricRow({ children }: { children: React.ReactNode }) {
  return (
    <div className="flex flex-wrap items-baseline gap-x-8 gap-y-2 text-sm text-cat-gray">
      {children}
    </div>
  );
}

export function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <span>
      <span className="text-cat-gray">{label} </span>
      <span className="font-semibold tabular-nums text-cat-black">{value}</span>
    </span>
  );
}
