import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useData } from '../hooks/useData';

const TYPES = ['Excavator', 'Bulldozer', 'Crane', 'Grader', 'Loader', 'Other'];

/**
 * Query form — user enters equipment rental data; it appends into the live fleet
 * and re-runs status / anomaly / alert / hybrid dashboard pipelines.
 */
export function DataEntryPage() {
  const { refresh } = useData();
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [form, setForm] = useState({
    equipment_id: '',
    type: 'Excavator',
    site_id: '',
    check_in_date: '',
    check_out_date: '',
    engine_hours_per_day: '',
    idle_hours_per_day: '',
    rental_days: '',
    last_operator_id: '',
    expected_return_date: '',
  });

  function set<K extends keyof typeof form>(key: K, value: string) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function randomFill() {
    const n = Math.floor(1000 + Math.random() * 9000);
    const types = TYPES.slice(0, 5);
    const sites = ['S001', 'S002', 'S003', 'S004', 'S006', ''];
    const ops = ['OP101', 'OP106', 'OP114', 'OP203', 'OP301', ''];
    const type = types[Math.floor(Math.random() * types.length)];
    const site = sites[Math.floor(Math.random() * sites.length)];
    const op = ops[Math.floor(Math.random() * ops.length)];
    const engine = (Math.random() * 9).toFixed(1);
    const idle = (Math.random() * 12).toFixed(1);
    const start = new Date();
    start.setDate(start.getDate() - Math.floor(Math.random() * 40));
    const end = new Date(start);
    end.setDate(end.getDate() + 10 + Math.floor(Math.random() * 20));
    const active = Math.random() > 0.55;
    setForm({
      equipment_id: `EQX${n}`,
      type,
      site_id: site,
      check_in_date: start.toISOString().slice(0, 10),
      check_out_date: active ? '' : end.toISOString().slice(0, 10),
      engine_hours_per_day: engine,
      idle_hours_per_day: idle,
      rental_days: active ? '' : String(Math.round((end.getTime() - start.getTime()) / 86400000)),
      last_operator_id: op,
      expected_return_date: active
        ? new Date(Date.now() + (2 + Math.floor(Math.random() * 10)) * 86400000)
            .toISOString()
            .slice(0, 10)
        : '',
    });
  }

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const body: Record<string, unknown> = {
        equipment_id: form.equipment_id.trim().toUpperCase(),
        type: form.type.trim(),
        site_id: form.site_id.trim() || null,
        last_operator_id: form.last_operator_id.trim() || null,
        check_in_date: form.check_in_date || null,
        check_out_date: form.check_out_date || null,
        expected_return_date: form.expected_return_date || null,
        engine_hours_per_day:
          form.engine_hours_per_day === '' ? null : Number(form.engine_hours_per_day),
        idle_hours_per_day: form.idle_hours_per_day === '' ? null : Number(form.idle_hours_per_day),
        rental_days: form.rental_days === '' ? null : Number(form.rental_days),
      };
      const res: any = await api.appendEquipment(body);
      setMessage(res.message || 'Appended successfully.');
      await refresh(false);
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page max-w-2xl">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-cat-gray">
            Query form · Live append
          </p>
          <h2 className="page-title">Add Equipment Data</h2>
          <p className="page-sub">
            Enter any rental row — it appends into the fleet and refreshes status, anomalies, alerts,
            and the hybrid dashboard automatically.
          </p>
        </div>
        <button type="button" onClick={randomFill} className="btn-primary">
          Fill random sample
        </button>
      </div>

      {message && (
        <div className="flex flex-wrap items-center gap-3 text-sm text-emerald-700">
          <span>{message}</span>
          <button type="button" className="underline" onClick={() => navigate('/')}>
            Open Command Center
          </button>
          <button
            type="button"
            className="underline"
            onClick={() => navigate(`/assets/${form.equipment_id.toUpperCase()}`)}
          >
            View equipment
          </button>
        </div>
      )}
      {error && <p className="text-sm text-red-700">{error}</p>}

      <form onSubmit={submit} className="space-y-5">
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Equipment ID *">
            <input
              required
              className="field w-full"
              value={form.equipment_id}
              onChange={(e) => set('equipment_id', e.target.value.toUpperCase())}
              placeholder="EQX2001"
            />
          </Field>
          <Field label="Type *">
            <select className="field w-full" value={form.type} onChange={(e) => set('type', e.target.value)}>
              {TYPES.map((t) => (
                <option key={t} value={t}>
                  {t}
                </option>
              ))}
            </select>
          </Field>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Site ID (blank / NULL allowed)">
            <input
              className="field w-full"
              value={form.site_id}
              onChange={(e) => set('site_id', e.target.value.toUpperCase())}
              placeholder="S003 or empty"
            />
          </Field>
          <Field label="Last Operator ID (blank / NULL allowed)">
            <input
              className="field w-full"
              value={form.last_operator_id}
              onChange={(e) => set('last_operator_id', e.target.value.toUpperCase())}
              placeholder="OP101 or empty"
            />
          </Field>
        </div>

        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Check-In Date (Dispatch / rented out)">
            <input
              type="date"
              className="field w-full"
              value={form.check_in_date}
              onChange={(e) => set('check_in_date', e.target.value)}
            />
          </Field>
          <Field label="Check-Out Date (Return — leave empty if still out)">
            <input
              type="date"
              className="field w-full"
              value={form.check_out_date}
              onChange={(e) => set('check_out_date', e.target.value)}
            />
          </Field>
        </div>

        <Field label="Expected Return Date (for active rentals / overdue engine)">
          <input
            type="date"
            className="field w-full"
            value={form.expected_return_date}
            onChange={(e) => set('expected_return_date', e.target.value)}
          />
        </Field>

        <div className="grid gap-5 sm:grid-cols-3">
          <Field label="Engine Hours/Day">
            <input
              type="number"
              step="0.1"
              min="0"
              className="field w-full"
              value={form.engine_hours_per_day}
              onChange={(e) => set('engine_hours_per_day', e.target.value)}
            />
          </Field>
          <Field label="Idle Hours/Day">
            <input
              type="number"
              step="0.1"
              min="0"
              className="field w-full"
              value={form.idle_hours_per_day}
              onChange={(e) => set('idle_hours_per_day', e.target.value)}
            />
          </Field>
          <Field label="Rental Days">
            <input
              type="number"
              min="0"
              className="field w-full"
              value={form.rental_days}
              onChange={(e) => set('rental_days', e.target.value)}
            />
          </Field>
        </div>

        <button type="submit" disabled={busy} className="btn-accent">
          {busy ? 'Appending & refreshing pipeline…' : 'Append to Dashboard'}
        </button>
      </form>
    </div>
  );
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <label className="block space-y-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-cat-gray">
      {label}
      {children}
    </label>
  );
}
