import clsx from 'clsx';
import type { EquipmentStatus } from '../types';

const STYLES: Record<string, string> = {
  AVAILABLE: 'text-emerald-700',
  RENTED: 'text-sky-700',
  'DUE SOON': 'text-amber-700',
  OVERDUE: 'text-red-700',
  'UNDER-UTILIZED': 'text-orange-700',
  ANOMALY: 'text-cat-dark',
};

export function StatusBadge({ status }: { status: EquipmentStatus | string | null }) {
  if (!status) return <span className="text-xs text-cat-gray">—</span>;
  return (
    <span
      className={clsx(
        'inline-flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wide',
        STYLES[status] || 'text-cat-gray',
      )}
      title={status}
    >
      <span aria-hidden className="h-1.5 w-1.5 bg-current" />
      {status}
    </span>
  );
}
