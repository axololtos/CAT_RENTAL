import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { useData } from '../hooks/useData';
import type { AppSettings } from '../types';
import { LoadingState, ErrorState } from '../components/States';

export function SettingsPage() {
  const { reloadSettings, refresh } = useData();
  const [form, setForm] = useState<AppSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    api.settings().then(setForm).catch((e) => setError(e.message));
  }, []);

  if (!form && !error) return <LoadingState />;
  if (error && !form) return <ErrorState message={error} />;
  if (!form) return null;

  async function save(e: React.FormEvent) {
    e.preventDefault();
    if (!form) return;
    setBusy(true);
    setMessage(null);
    setError(null);
    try {
      const updated = await api.updateSettings({ ...form });
      setForm(updated);
      await reloadSettings();
      await refresh(true);
      setMessage('Settings saved and data refreshed.');
    } catch (err: any) {
      setError(err.message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="page max-w-xl">
      <div>
        <h2 className="page-title">Settings</h2>
        <p className="page-sub">Data source, refresh interval, and detection thresholds.</p>
      </div>

      {message && <p className="text-sm text-emerald-700">{message}</p>}
      {error && <p className="text-sm text-red-700">{error}</p>}

      <form onSubmit={save} className="space-y-6">
        <Field label="Data Source Type">
          <select
            className="field w-full"
            value={form.data_source_type}
            onChange={(e) => setForm({ ...form, data_source_type: e.target.value })}
          >
            <option value="local">Local CSV</option>
            <option value="cloud">Cloud CSV URL</option>
          </select>
        </Field>

        <Field label="Cloud CSV URL">
          <input
            className="field w-full"
            value={form.cloud_csv_url || ''}
            onChange={(e) => setForm({ ...form, cloud_csv_url: e.target.value })}
            placeholder="https://…"
          />
        </Field>

        <Field label="Refresh Interval (seconds)">
          <input
            type="number"
            min={5}
            className="field w-full"
            value={form.refresh_interval_seconds}
            onChange={(e) => setForm({ ...form, refresh_interval_seconds: Number(e.target.value) })}
          />
        </Field>

        <div className="grid gap-5 sm:grid-cols-3">
          <Field label="Util Low Max">
            <input
              type="number"
              className="field w-full"
              value={form.util_low_max}
              onChange={(e) => setForm({ ...form, util_low_max: Number(e.target.value) })}
            />
          </Field>
          <Field label="Util Moderate Max">
            <input
              type="number"
              className="field w-full"
              value={form.util_moderate_max}
              onChange={(e) => setForm({ ...form, util_moderate_max: Number(e.target.value) })}
            />
          </Field>
          <Field label="Util Good Max">
            <input
              type="number"
              className="field w-full"
              value={form.util_good_max}
              onChange={(e) => setForm({ ...form, util_good_max: Number(e.target.value) })}
            />
          </Field>
        </div>

        <Field label="Idle-Hour Anomaly Threshold">
          <input
            type="number"
            className="field w-full"
            value={form.idle_hours_anomaly_threshold}
            onChange={(e) => setForm({ ...form, idle_hours_anomaly_threshold: Number(e.target.value) })}
          />
        </Field>

        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Due-Soon Days">
            <input
              type="number"
              className="field w-full"
              value={form.due_soon_days}
              onChange={(e) => setForm({ ...form, due_soon_days: Number(e.target.value) })}
            />
          </Field>
          <Field label="Forecast Horizon">
            <input
              type="number"
              className="field w-full"
              value={form.forecast_horizon_days}
              onChange={(e) => setForm({ ...form, forecast_horizon_days: Number(e.target.value) })}
            />
          </Field>
        </div>

        <label className="flex items-center gap-2 text-sm">
          <input
            type="checkbox"
            checked={form.use_demo_forecast_data}
            onChange={(e) => setForm({ ...form, use_demo_forecast_data: e.target.checked })}
          />
          Demo forecast historical data (separate from production)
        </label>

        <button type="submit" disabled={busy} className="btn-accent">
          {busy ? 'Saving…' : 'Save Settings'}
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
