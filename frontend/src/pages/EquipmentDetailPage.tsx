import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { QRCodeSVG } from 'qrcode.react';
import { api } from '../services/api';
import { useData } from '../hooks/useData';
import { StatusBadge } from '../components/StatusBadge';
import { AlertCard } from '../components/AlertCard';
import { LoadingState, ErrorState } from '../components/States';
import type { Anomaly, Alert, Recommendation, RentalTransaction, Equipment } from '../types';

export function EquipmentDetailPage() {
  const { id } = useParams();
  const { tick } = useData();
  const [equipment, setEquipment] = useState<Equipment | null>(null);
  const [anomalies, setAnomalies] = useState<Anomaly[]>([]);
  const [alerts, setAlerts] = useState<Alert[]>([]);
  const [recs, setRecs] = useState<Recommendation[]>([]);
  const [history, setHistory] = useState<RentalTransaction[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!id) return;
    setLoading(true);
    api
      .equipmentDetail(id)
      .then((res: any) => {
        setEquipment(res.equipment);
        setAnomalies(res.anomalies || []);
        setAlerts(res.alerts || []);
        setRecs(res.recommendations || []);
        setHistory(res.rental_history || []);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id, tick]);

  if (loading) return <LoadingState />;
  if (error) return <ErrorState message={error} />;
  if (!equipment) return null;

  return (
    <div className="page">
      <div className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <Link to="/assets" className="text-xs font-semibold text-cat-gray hover:text-cat-black">
            ← Assets
          </Link>
          <div className="mt-2 flex flex-wrap items-center gap-3">
            <h2 className="page-title">{equipment.equipment_id}</h2>
            <StatusBadge status={equipment.status} />
          </div>
          <p className="page-sub">{equipment.type}</p>
        </div>
        <QRCodeSVG value={equipment.equipment_id} size={88} />
      </div>

      <dl className="grid gap-x-8 gap-y-5 border-y border-cat-muted py-5 sm:grid-cols-2 lg:grid-cols-4">
        <Item label="Site" value={equipment.site_id || '—'} />
        <Item label="Operator" value={equipment.last_operator_id || '—'} />
        <Item label="Check-In (Rented Out)" value={equipment.check_in_date || '—'} />
        <Item label="Check-Out (Returned)" value={equipment.check_out_date || '—'} />
        <Item label="Expected Return" value={equipment.expected_return_date || '—'} />
        <Item label="Rental Days" value={equipment.rental_days ?? '—'} />
        <Item label="Engine / Idle" value={`${equipment.engine_hours_per_day ?? '—'} / ${equipment.idle_hours_per_day ?? '—'}`} />
        <Item
          label="Utilization"
          value={
            equipment.utilization_pct != null
              ? `${equipment.utilization_pct}% · ${equipment.utilization_category}`
              : '—'
          }
        />
      </dl>

      <div className="grid gap-10 lg:grid-cols-2">
        <div>
          <h3 className="section-label">Alerts</h3>
          {alerts.length === 0 && <p className="text-sm text-cat-gray">None</p>}
          {alerts.map((a) => (
            <AlertCard
              key={a.id}
              title={a.title}
              message={a.message}
              severity={a.severity}
              time={a.detected_at}
            />
          ))}
        </div>
        <div>
          <h3 className="section-label">Recommendations</h3>
          {recs.length === 0 && <p className="text-sm text-cat-gray">None</p>}
          {recs.map((r) => (
            <div key={r.id} className="border-b border-cat-muted py-3 text-sm last:border-0">
              <span className="text-[10px] font-bold uppercase text-cat-gray">{r.priority}</span>
              <p className="mt-0.5">{r.message}</p>
            </div>
          ))}
        </div>
      </div>

      <div>
        <h3 className="section-label">Anomalies</h3>
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-cat-black text-[10px] uppercase tracking-[0.12em] text-cat-gray">
              <th className="pb-2 text-left font-semibold">Source</th>
              <th className="pb-2 text-left font-semibold">Severity</th>
              <th className="pb-2 text-left font-semibold">Reason</th>
            </tr>
          </thead>
          <tbody>
            {anomalies.map((a) => (
              <tr key={a.id} className="border-b border-cat-muted">
                <td className="py-2">{a.source === 'ML' ? 'Potential (ML)' : 'Rule'}</td>
                <td className="py-2">{a.severity}</td>
                <td className="py-2">{a.reason}</td>
              </tr>
            ))}
            {anomalies.length === 0 && (
              <tr>
                <td colSpan={3} className="py-4 text-cat-gray">
                  No anomalies
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      <div>
        <h3 className="section-label">Rental history</h3>
        <table className="min-w-full text-sm">
          <thead>
            <tr className="border-b border-cat-black text-[10px] uppercase tracking-[0.12em] text-cat-gray">
              <th className="pb-2 text-left font-semibold">Type</th>
              <th className="pb-2 text-left font-semibold">Date</th>
              <th className="pb-2 text-left font-semibold">Site</th>
              <th className="pb-2 text-left font-semibold">Notes</th>
            </tr>
          </thead>
          <tbody>
            {history.map((h) => (
              <tr key={h.id} className="border-b border-cat-muted">
                <td className="py-2 font-semibold">
                  {h.transaction_type === 'CHECK_IN' ? 'Check-In' : 'Check-Out'}
                </td>
                <td className="py-2">{h.transaction_date}</td>
                <td className="py-2">{h.site_id || '—'}</td>
                <td className="py-2">{h.condition_notes || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

function Item({ label, value }: { label: string; value: string | number }) {
  return (
    <div>
      <dt className="text-[10px] font-semibold uppercase tracking-[0.12em] text-cat-gray">{label}</dt>
      <dd className="mt-1 text-sm font-medium">{value}</dd>
    </div>
  );
}
