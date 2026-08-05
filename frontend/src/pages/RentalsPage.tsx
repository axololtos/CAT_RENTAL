import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { useData } from '../hooks/useData';
import type { RentalTransaction } from '../types';
import { LoadingState, ErrorState } from '../components/States';

export function RentalsPage() {
  const { tick } = useData();
  const [items, setItems] = useState<RentalTransaction[]>([]);
  const [equipmentId, setEquipmentId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    api
      .rentals(equipmentId || undefined)
      .then((d) => {
        setItems(d);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tick, equipmentId]);

  return (
    <div className="page">
      <div>
        <h2 className="page-title">Rental History</h2>
        <p className="page-sub">
          Available → Check-In → On site → Return approaching → Check-Out → Available
        </p>
      </div>

      <input
        className="max-w-xs border-0 border-b border-cat-muted bg-transparent py-2 text-sm outline-none focus:border-cat-yellow"
        placeholder="Filter by Equipment ID"
        value={equipmentId}
        onChange={(e) => setEquipmentId(e.target.value.toUpperCase())}
      />

      {loading && <LoadingState />}
      {error && <ErrorState message={error} />}

      {!loading && !error && (
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-cat-black text-[10px] uppercase tracking-[0.12em] text-cat-gray">
              <th className="pb-2 text-left font-semibold">Equipment</th>
              <th className="pb-2 text-left font-semibold">Transaction</th>
              <th className="pb-2 text-left font-semibold">Date</th>
              <th className="pb-2 text-left font-semibold">Site</th>
              <th className="pb-2 text-left font-semibold">Operator</th>
              <th className="pb-2 text-left font-semibold">Notes</th>
            </tr>
          </thead>
          <tbody>
            {items.map((t) => (
              <tr key={t.id} className="border-b border-cat-muted">
                <td className="py-2.5 font-semibold">
                  <Link className="hover:underline" to={`/assets/${t.equipment_id}`}>
                    {t.equipment_id}
                  </Link>
                </td>
                <td className="py-2.5">
                  {t.transaction_type === 'CHECK_IN' ? 'Check-In (Out)' : 'Check-Out (Return)'}
                </td>
                <td className="py-2.5 tabular-nums">{t.transaction_date}</td>
                <td className="py-2.5">{t.site_id || '—'}</td>
                <td className="py-2.5">{t.operator_id || '—'}</td>
                <td className="py-2.5 text-cat-gray">{t.condition_notes || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      )}
    </div>
  );
}
