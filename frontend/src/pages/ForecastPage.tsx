import { useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../services/api';
import { useData } from '../hooks/useData';
import type { ForecastResult } from '../types';
import { ChartCard } from '../components/ChartCard';
import { KPICard, KPIStrip } from '../components/KPICard';
import { LoadingState, ErrorState, EmptyState } from '../components/States';

export function ForecastPage() {
  const { tick, reloadSettings } = useData();
  const [data, setData] = useState<ForecastResult | null>(null);
  const [horizon, setHorizon] = useState(30);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [enablingDemo, setEnablingDemo] = useState(false);

  useEffect(() => {
    setLoading(true);
    api
      .forecast(horizon)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tick, horizon]);

  async function enableDemo() {
    setEnablingDemo(true);
    try {
      await api.updateSettings({ use_demo_forecast_data: true });
      await reloadSettings();
      const d = await api.forecast(horizon);
      setData(d);
    } catch (e: any) {
      setError(e.message);
    } finally {
      setEnablingDemo(false);
    }
  }

  if (loading && !data) return <LoadingState label="Running forecast…" />;
  if (error && !data) return <ErrorState message={error} />;
  if (!data) return null;

  const chartData = data.items.slice(0, 12).map((i) => ({
    label: `${i.equipment_type}@${i.site_id}`,
    demand: i.predicted_demand,
  }));

  return (
    <div className="page">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="page-title">Demand Forecast</h2>
          <p className="page-sub">Equipment type demand by site for pre-positioning.</p>
        </div>
        <div className="flex gap-4 text-sm">
          {[7, 30].map((h) => (
            <button
              key={h}
              type="button"
              onClick={() => setHorizon(h)}
              className={`pb-1 font-semibold ${horizon === h ? 'border-b-2 border-cat-yellow' : 'text-cat-gray'}`}
            >
              Next {h} days
            </button>
          ))}
        </div>
      </div>

      {data.demo_mode && (
        <p className="text-sm text-amber-800">
          Demo mode — generated sample history only, not mixed with production data.
        </p>
      )}

      {!data.sufficient_data ? (
        <div className="space-y-4">
          <EmptyState
            title="Insufficient historical data for reliable ML forecasting."
            description={data.message}
          />
          <button type="button" disabled={enablingDemo} onClick={enableDemo} className="btn-primary">
            {enablingDemo ? 'Enabling…' : 'Enable Demo Forecast Mode'}
          </button>
        </div>
      ) : (
        <>
          <KPIStrip>
            <KPICard label="Model" value={data.model_name} />
            <KPICard label="MAE" value={data.mae?.toFixed(3) ?? '—'} />
            <KPICard label="RMSE" value={data.rmse?.toFixed(3) ?? '—'} />
            <KPICard label="Horizon" value={`${data.horizon_days}d`} accent="yellow" />
            <KPICard label="Predictions" value={data.items.length} />
            <KPICard label="High demand" value={data.items.filter((i) => i.demand_level === 'HIGH').length} />
          </KPIStrip>
          <p className="text-xs text-cat-gray">{data.message}</p>

          <ChartCard title="Top predicted demand">
            <div className="h-64">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={chartData} barCategoryGap="28%">
                  <CartesianGrid vertical={false} stroke="#e8e8e4" />
                  <XAxis dataKey="label" tick={{ fontSize: 9, fill: '#5c5c5c' }} interval={0} angle={-20} textAnchor="end" height={60} axisLine={false} tickLine={false} />
                  <YAxis tick={{ fontSize: 11, fill: '#5c5c5c' }} axisLine={false} tickLine={false} width={28} />
                  <Tooltip />
                  <Bar dataKey="demand" fill="#ffcd11" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>

          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-cat-black text-[10px] uppercase tracking-[0.12em] text-cat-gray">
                <th className="pb-2 text-left font-semibold">Type</th>
                <th className="pb-2 text-left font-semibold">Site</th>
                <th className="pb-2 text-left font-semibold">Demand</th>
                <th className="pb-2 text-left font-semibold">Level</th>
                <th className="pb-2 text-left font-semibold">Confidence</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((item, i) => (
                <tr key={i} className="border-b border-cat-muted">
                  <td className="py-2.5 font-semibold">{item.equipment_type}</td>
                  <td className="py-2.5">{item.site_id}</td>
                  <td className="py-2.5 tabular-nums">{item.predicted_demand}</td>
                  <td className="py-2.5 text-[11px] font-bold uppercase">{item.demand_level}</td>
                  <td className="py-2.5 text-cat-gray">{item.confidence || '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </>
      )}
    </div>
  );
}
