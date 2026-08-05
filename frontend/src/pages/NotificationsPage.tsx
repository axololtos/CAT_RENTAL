import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { api } from '../services/api';
import { useData } from '../hooks/useData';
import type { Alert } from '../types';
import { LoadingState, ErrorState, EmptyState } from '../components/States';

const CATEGORIES = ['', 'OVERDUE', 'RETURN APPROACHING', 'ANOMALY', 'LOW UTILIZATION', 'DATA SOURCE ERROR'];
const select =
  'border-0 border-b border-cat-muted bg-transparent py-2 text-sm outline-none focus:border-cat-yellow';

export function NotificationsPage() {
  const { tick, refresh } = useData();
  const [items, setItems] = useState<Alert[]>([]);
  const [category, setCategory] = useState('');
  const [severity, setSeverity] = useState('');
  const [equipmentId, setEquipmentId] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (category) params.category = category;
    if (severity) params.severity = severity;
    if (equipmentId) params.equipment_id = equipmentId;
    api
      .notifications(params)
      .then((d) => {
        setItems(d);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tick, category, severity, equipmentId]);

  async function toggleRead(id: string, read: boolean) {
    await api.markRead(id, read);
    await refresh(false);
  }

  return (
    <div className="page max-w-3xl">
      <div>
        <h2 className="page-title">Notifications</h2>
        <p className="page-sub">Overdue, return approaching, anomalies, and data issues.</p>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-3">
        <select className={select} value={category} onChange={(e) => setCategory(e.target.value)}>
          {CATEGORIES.map((c) => (
            <option key={c || 'all'} value={c}>
              {c || 'All Categories'}
            </option>
          ))}
        </select>
        <select className={select} value={severity} onChange={(e) => setSeverity(e.target.value)}>
          <option value="">All Severities</option>
          {['CRITICAL', 'OVERDUE', 'URGENT', 'WARNING', 'REMINDER', 'INFO'].map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
        <input
          className={select}
          placeholder="Equipment ID"
          value={equipmentId}
          onChange={(e) => setEquipmentId(e.target.value.toUpperCase())}
        />
      </div>

      {loading && <LoadingState />}
      {error && <ErrorState message={error} />}
      {!loading && !error && items.length === 0 && (
        <EmptyState title="No notifications" description="Alerts appear here as conditions change." />
      )}

      <div>
        {items.map((n) => (
          <div
            key={n.id}
            className={`flex gap-4 border-b border-cat-muted py-4 ${n.read ? 'opacity-50' : ''}`}
          >
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-wide text-cat-gray">
                <span>{n.category}</span>
                <span>{n.severity}</span>
                {!n.read && <span className="bg-cat-yellow px-1.5 text-cat-black">New</span>}
              </div>
              <h3 className="mt-1 text-sm font-semibold">{n.title}</h3>
              <p className="mt-0.5 text-sm text-cat-gray">{n.message}</p>
              <div className="mt-1 flex gap-3 text-[11px] text-cat-gray">
                {n.equipment_id && (
                  <Link className="font-semibold text-cat-black hover:underline" to={`/assets/${n.equipment_id}`}>
                    {n.equipment_id}
                  </Link>
                )}
                <span>{new Date(n.detected_at).toLocaleString()}</span>
              </div>
            </div>
            <button
              type="button"
              onClick={() => toggleRead(n.id, !n.read)}
              className="shrink-0 self-start text-xs font-semibold text-cat-gray hover:text-cat-black"
            >
              {n.read ? 'Unread' : 'Read'}
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
