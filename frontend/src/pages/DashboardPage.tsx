import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { Cloud, Cpu, Radio, ShieldAlert } from 'lucide-react';
import { api } from '../services/api';
import { useData } from '../hooks/useData';
import type { HybridDashboard } from '../types';
import { KPICard, KPIStrip } from '../components/KPICard';
import { ChartCard } from '../components/ChartCard';
import { LoadingState, ErrorState } from '../components/States';

export function DashboardPage() {
  const { tick } = useData();
  const navigate = useNavigate();
  const [data, setData] = useState<HybridDashboard | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .hybridDashboard()
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tick]);

  if (loading && !data) return <LoadingState label="Loading hybrid-cloud fleet view…" />;
  if (error && !data) return <ErrorState message={error} onRetry={() => window.location.reload()} />;
  if (!data) return null;

  const { kpis } = data;
  const utilByType = Object.values(
    data.live_state.reduce<Record<string, { type: string; util: number; n: number }>>((acc, s) => {
      const t = s.equipment_type;
      if (!acc[t]) acc[t] = { type: t, util: 0, n: 0 };
      acc[t].util += s.utilization_pct || 0;
      acc[t].n += 1;
      return acc;
    }, {}),
  ).map((x) => ({ type: x.type, utilization: Math.round(x.util / x.n) }));

  const edgeOnline = data.topology.edge.filter((c) => c.status === 'ONLINE').length;
  const cloudOnline = data.topology.cloud.filter((c) => c.status === 'ONLINE').length;

  return (
    <div className="page">
      <div className="flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-cat-gray">
            Hybrid-Cloud Operations
          </p>
          <h2 className="page-title">Fleet Command Center</h2>
          <p className="page-sub">
            Edge Greengrass + AWS IoT · Contracts & live telemetry · Real-time misuse rules
          </p>
        </div>
        <div className="flex flex-wrap gap-4 text-xs">
          <StatusPill icon={<Cpu size={13} />} label="Edge" value={`${edgeOnline}/${data.topology.edge.length}`} />
          <StatusPill icon={<Cloud size={13} />} label="AWS" value={`${cloudOnline}/${data.topology.cloud.length}`} />
          <StatusPill icon={<Radio size={13} />} label="MQTT" value="fleet/telemetry/v1" />
          <Link to="/architecture" className="btn-primary">
            Architecture
          </Link>
        </div>
      </div>

      <KPIStrip>
        <KPICard label="Fleet" value={kpis.fleet_size} />
        <KPICard label="Active Contracts" value={kpis.active_contracts} accent="yellow" />
        <KPICard label="Returned" value={kpis.returned_contracts} accent="success" />
        <KPICard label="Unassigned Usage" value={kpis.unassigned_usage} accent="danger" />
        <KPICard label="Under-Utilized" value={kpis.under_utilized} accent="warning" />
        <KPICard label="Critical Anomalies" value={kpis.critical_anomalies} accent="danger" />
      </KPIStrip>

      <div className="flex flex-wrap gap-x-8 gap-y-2 text-sm text-cat-gray">
        <span>
          Live assets <strong className="text-cat-black">{kpis.live_assets_online}</strong>
        </span>
        <span>
          Avg fuel <strong className="text-cat-black">{kpis.avg_fuel_pct}%</strong>
        </span>
        <span>
          Avg utilization <strong className="text-cat-black">{kpis.avg_utilization_pct}%</strong>
        </span>
        <span>
          Overdue <strong className="text-cat-black">{kpis.overdue_alerts}</strong>
        </span>
        <span>
          Return reminders <strong className="text-cat-black">{kpis.return_reminders}</strong>
        </span>
      </div>

      {/* Dual-layer strip */}
      <div className="grid gap-8 lg:grid-cols-2">
        <div>
          <h3 className="section-label">On-site / Edge</h3>
          <div className="space-y-2">
            {data.topology.edge.map((c) => (
              <ComponentRow key={c.id} name={c.name} status={c.status} detail={c.detail} />
            ))}
          </div>
        </div>
        <div>
          <h3 className="section-label">AWS Cloud Backend</h3>
          <div className="space-y-2">
            {data.topology.cloud.slice(0, 6).map((c) => (
              <ComponentRow key={c.id} name={c.name} status={c.status} />
            ))}
            <button
              type="button"
              className="text-xs font-semibold text-cat-gray hover:text-cat-black"
              onClick={() => navigate('/architecture')}
            >
              View full topology →
            </button>
          </div>
        </div>
      </div>

      {/* Live state table */}
      <div>
        <div className="mb-3 flex items-baseline justify-between">
          <h3 className="section-label mb-0">Equipment Live State</h3>
          <span className="text-[11px] text-cat-gray">DynamoDB · EquipmentLiveState</span>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-cat-black text-[10px] uppercase tracking-[0.12em] text-cat-gray">
                <th className="pb-2 pr-3 text-left font-semibold">Equipment</th>
                <th className="pb-2 pr-3 text-left font-semibold">Type</th>
                <th className="pb-2 pr-3 text-left font-semibold">Site</th>
                <th className="pb-2 pr-3 text-left font-semibold">Operator</th>
                <th className="pb-2 pr-3 text-left font-semibold">Fuel</th>
                <th className="pb-2 pr-3 text-left font-semibold">Engine</th>
                <th className="pb-2 pr-3 text-left font-semibold">Idle</th>
                <th className="pb-2 pr-3 text-left font-semibold">Util</th>
                <th className="pb-2 pr-3 text-left font-semibold">Gateway</th>
                <th className="pb-2 text-left font-semibold">Anomaly</th>
              </tr>
            </thead>
            <tbody>
              {data.live_state.map((s) => (
                <tr
                  key={s.equipment_id}
                  className={`cursor-pointer border-b border-cat-muted hover:bg-cat-yellow/15 ${
                    s.anomaly_status !== 'NORMAL' ? 'bg-red-50/40' : ''
                  }`}
                  onClick={() => navigate(`/assets/${s.equipment_id}`)}
                >
                  <td className="py-2.5 pr-3 font-semibold">{s.equipment_id}</td>
                  <td className="py-2.5 pr-3">{s.equipment_type}</td>
                  <td className="py-2.5 pr-3">{s.site_id || 'NULL'}</td>
                  <td className="py-2.5 pr-3">{s.last_operator_id || 'NULL'}</td>
                  <td className="py-2.5 pr-3 tabular-nums">{s.fuel_pct}%</td>
                  <td className="py-2.5 pr-3 tabular-nums">{s.engine_hours}</td>
                  <td className="py-2.5 pr-3 tabular-nums">{s.idle_hours}</td>
                  <td className="py-2.5 pr-3 tabular-nums">
                    {s.utilization_pct != null ? `${s.utilization_pct}%` : '—'}
                  </td>
                  <td className="py-2.5 pr-3 text-xs text-cat-gray">{s.gateway_id}</td>
                  <td className="py-2.5">
                    <AnomalyTag status={s.anomaly_status} />
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      <div className="grid gap-10 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <h3 className="section-label">Architecture Anomaly Engine</h3>
          <p className="mb-3 text-xs text-cat-gray">
            IoT Rule → Anomaly Lambda · UNASSIGNED_USAGE · UNDER_UTILIZED · MISSING_OPERATOR
          </p>
          {data.architecture_anomalies.length === 0 && (
            <p className="text-sm text-cat-gray">No architecture-rule anomalies.</p>
          )}
          {data.architecture_anomalies.map((a) => (
            <button
              key={a.id}
              type="button"
              onClick={() => navigate(`/assets/${a.equipment_id}`)}
              className="flex w-full gap-3 border-b border-cat-muted py-3 text-left hover:bg-cat-light/80"
            >
              <ShieldAlert
                size={16}
                className={a.severity === 'CRITICAL' ? 'mt-0.5 text-red-600' : 'mt-0.5 text-amber-600'}
              />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-sm font-semibold">{a.title}</span>
                  <span className="text-[10px] font-bold uppercase tracking-wide text-cat-gray">
                    {a.rule}
                  </span>
                  <span className="text-[10px] font-bold uppercase text-cat-gray">{a.severity}</span>
                </div>
                <p className="mt-0.5 text-xs text-cat-gray line-clamp-2">{a.reason}</p>
                <p className="mt-1 text-[11px] text-cat-gray">
                  {a.equipment_id} · {a.layer}
                </p>
              </div>
            </button>
          ))}
        </div>

        <div className="space-y-8">
          <ChartCard title="Utilization by type">
            <div className="h-44">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={utilByType} barCategoryGap="30%">
                  <CartesianGrid vertical={false} stroke="#e8e8e4" />
                  <XAxis dataKey="type" tick={{ fontSize: 10, fill: '#5c5c5c' }} axisLine={false} tickLine={false} />
                  <YAxis unit="%" tick={{ fontSize: 10, fill: '#5c5c5c' }} axisLine={false} tickLine={false} width={32} />
                  <Tooltip />
                  <Bar dataKey="utilization" fill="#ffcd11" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </ChartCard>

          <div>
            <h3 className="section-label">Workflow</h3>
            <div className="space-y-3 text-sm">
              <div className="border-l-2 border-cat-yellow pl-3">
                <p className="font-semibold">{data.workflow.dispatch.architecture_name}</p>
                <p className="text-xs text-cat-gray">{data.workflow.dispatch.description}</p>
              </div>
              <div className="border-l-2 border-cat-black pl-3">
                <p className="font-semibold">{data.workflow.return.architecture_name}</p>
                <p className="text-xs text-cat-gray">{data.workflow.return.description}</p>
              </div>
              <Link to="/check-in-out" className="inline-block text-xs font-semibold underline">
                Open Dispatch / Return console
              </Link>
            </div>
          </div>
        </div>
      </div>

      {/* Contracts */}
      <div>
        <div className="mb-3 flex items-baseline justify-between">
          <h3 className="section-label mb-0">Rental Contracts</h3>
          <span className="text-[11px] text-cat-gray">DynamoDB · RentalContracts</span>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-cat-black text-[10px] uppercase tracking-[0.12em] text-cat-gray">
                <th className="pb-2 pr-3 text-left font-semibold">Equipment</th>
                <th className="pb-2 pr-3 text-left font-semibold">Site</th>
                <th className="pb-2 pr-3 text-left font-semibold">Dispatch Start</th>
                <th className="pb-2 pr-3 text-left font-semibold">Return End</th>
                <th className="pb-2 pr-3 text-left font-semibold">Days</th>
                <th className="pb-2 text-left font-semibold">Status</th>
              </tr>
            </thead>
            <tbody>
              {data.contracts.map((c) => (
                <tr
                  key={c.equipment_id}
                  className="cursor-pointer border-b border-cat-muted hover:bg-cat-yellow/15"
                  onClick={() => navigate(`/assets/${c.equipment_id}`)}
                >
                  <td className="py-2.5 pr-3 font-semibold">{c.equipment_id}</td>
                  <td className="py-2.5 pr-3">{c.site_id || 'NULL'}</td>
                  <td className="py-2.5 pr-3 tabular-nums">{c.dispatch_date || '—'}</td>
                  <td className="py-2.5 pr-3 tabular-nums">{c.return_date || '—'}</td>
                  <td className="py-2.5 pr-3 tabular-nums">{c.rental_days ?? '—'}</td>
                  <td className="py-2.5 text-[11px] font-semibold uppercase tracking-wide">
                    {c.status}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>

      {data.demand_forecast_preview.length > 0 && (
        <div>
          <div className="mb-3 flex items-baseline justify-between">
            <h3 className="section-label mb-0">Demand Forecast Preview</h3>
            <Link to="/forecast" className="text-xs font-semibold underline">
              SageMaker pipeline
            </Link>
          </div>
          <div className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
            {data.demand_forecast_preview.map((f, i) => (
              <span key={i}>
                <strong>{f.equipment_type}</strong> @ {f.site_id} · {f.demand_level} ({f.predicted_demand})
              </span>
            ))}
          </div>
        </div>
      )}

      <p className="text-[11px] text-cat-gray">{data.topology.prototype_note}</p>
    </div>
  );
}

function StatusPill({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <span className="inline-flex items-center gap-1.5 text-cat-gray">
      {icon}
      <span className="font-semibold uppercase tracking-wide">{label}</span>
      <span className="text-cat-black">{value}</span>
    </span>
  );
}

function ComponentRow({
  name,
  status,
  detail,
}: {
  name: string;
  status: string;
  detail?: string;
}) {
  return (
    <div className="flex items-start justify-between gap-3 border-b border-cat-muted py-2 last:border-0">
      <div>
        <p className="text-sm font-medium">{name}</p>
        {detail && <p className="text-[11px] text-cat-gray">{detail}</p>}
      </div>
      <span className="text-[10px] font-bold uppercase tracking-wide text-emerald-700">{status}</span>
    </div>
  );
}

function AnomalyTag({ status }: { status: string }) {
  if (status === 'NORMAL') {
    return <span className="text-[11px] font-semibold uppercase text-emerald-700">Normal</span>;
  }
  return (
    <span className="text-[11px] font-semibold uppercase text-red-700">{status.replaceAll('_', ' ')}</span>
  );
}
