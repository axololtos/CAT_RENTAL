import { Link } from 'react-router-dom';
import type { Equipment } from '../types';
import { StatusBadge } from './StatusBadge';

interface Props {
  items: Equipment[];
  onRowClick?: (id: string) => void;
  compact?: boolean;
}

export function EquipmentTable({ items, onRowClick, compact }: Props) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-left text-sm">
        <thead>
          <tr className="border-b border-cat-black text-[10px] uppercase tracking-[0.12em] text-cat-gray">
            <th className="pb-2 pr-4 font-semibold">Equipment</th>
            <th className="pb-2 pr-4 font-semibold">Type</th>
            <th className="pb-2 pr-4 font-semibold">Site</th>
            <th className="pb-2 pr-4 font-semibold">Status</th>
            {!compact && (
              <>
                <th className="pb-2 pr-4 font-semibold">Check-In</th>
                <th className="pb-2 pr-4 font-semibold">Check-Out</th>
              </>
            )}
            <th className="pb-2 pr-4 font-semibold">Engine</th>
            <th className="pb-2 pr-4 font-semibold">Idle</th>
            {!compact && <th className="pb-2 pr-4 font-semibold">Days</th>}
            {!compact && <th className="pb-2 pr-4 font-semibold">Operator</th>}
            <th className="pb-2 pr-4 font-semibold">Util %</th>
            <th className="pb-2 font-semibold">Anomaly</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr
              key={r.equipment_id}
              className="cursor-pointer border-b border-cat-muted/80 transition-colors hover:bg-cat-yellow/15"
              onClick={() => onRowClick?.(r.equipment_id)}
            >
              <td className="py-2.5 pr-4 font-semibold">
                <Link
                  to={`/assets/${r.equipment_id}`}
                  className="text-cat-black hover:underline"
                  onClick={(e) => e.stopPropagation()}
                >
                  {r.equipment_id}
                </Link>
              </td>
              <td className="py-2.5 pr-4">{r.type}</td>
              <td className="py-2.5 pr-4">{r.site_id || '—'}</td>
              <td className="py-2.5 pr-4">
                <StatusBadge status={r.status} />
              </td>
              {!compact && (
                <>
                  <td className="py-2.5 pr-4 tabular-nums text-cat-dark">{r.check_in_date || '—'}</td>
                  <td className="py-2.5 pr-4 tabular-nums text-cat-dark">{r.check_out_date || '—'}</td>
                </>
              )}
              <td className="py-2.5 pr-4 tabular-nums">{r.engine_hours_per_day ?? '—'}</td>
              <td className="py-2.5 pr-4 tabular-nums">{r.idle_hours_per_day ?? '—'}</td>
              {!compact && (
                <td className="py-2.5 pr-4 tabular-nums">{r.rental_days ?? '—'}</td>
              )}
              {!compact && <td className="py-2.5 pr-4">{r.last_operator_id || '—'}</td>}
              <td className="py-2.5 pr-4 tabular-nums">
                {r.utilization_pct != null ? `${r.utilization_pct}%` : '—'}
              </td>
              <td className="py-2.5">
                {r.is_ml_anomaly || r.anomaly_flags.length > 0 ? (
                  <span className="text-[11px] font-semibold uppercase text-cat-dark">
                    {r.is_ml_anomaly ? 'Potential' : 'Flagged'}
                  </span>
                ) : (
                  <span className="text-cat-muted">—</span>
                )}
              </td>
            </tr>
          ))}
          {items.length === 0 && (
            <tr>
              <td colSpan={12} className="py-10 text-center text-sm text-cat-gray">
                No equipment matches the current filters.
              </td>
            </tr>
          )}
        </tbody>
      </table>
    </div>
  );
}
