import { useEffect, useState } from 'react';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Line,
  LineChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../services/api';
import { useData } from '../hooks/useData';
import type { AnalyticsData, Equipment } from '../types';
import { ChartCard } from '../components/ChartCard';
import { KPICard, KPIStrip } from '../components/KPICard';
import { LoadingState, ErrorState } from '../components/States';

const select =
  'border-0 border-b border-cat-muted bg-transparent py-2 text-sm outline-none focus:border-cat-yellow';

export function AnalyticsPage() {
  const { tick } = useData();
  const [data, setData] = useState<AnalyticsData | null>(null);
  const [equipment, setEquipment] = useState<Equipment[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [equipmentId, setEquipmentId] = useState('');
  const [equipmentType, setEquipmentType] = useState('');
  const [siteId, setSiteId] = useState('');

  useEffect(() => {
    api.equipment().then((r) => setEquipment(r.items));
  }, [tick]);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (equipmentId) params.equipment_id = equipmentId;
    if (equipmentType) params.equipment_type = equipmentType;
    if (siteId) params.site_id = siteId;
    api
      .analytics(params)
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tick, equipmentId, equipmentType, siteId]);

  const types = [...new Set(equipment.map((e) => e.type))].sort();
  const sites = [...new Set(equipment.map((e) => e.site_id).filter(Boolean) as string[])].sort();

  if (loading && !data) return <LoadingState />;
  if (error && !data) return <ErrorState message={error} />;
  if (!data) return null;

  return (
    <div className="page">
      <div>
        <h2 className="page-title">Usage Analytics</h2>
        <p className="page-sub">Runtime, idle time, site and operator usage.</p>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-3">
        <select className={select} value={equipmentId} onChange={(e) => setEquipmentId(e.target.value)}>
          <option value="">All Equipment</option>
          {equipment.map((e) => (
            <option key={e.equipment_id} value={e.equipment_id}>
              {e.equipment_id}
            </option>
          ))}
        </select>
        <select className={select} value={equipmentType} onChange={(e) => setEquipmentType(e.target.value)}>
          <option value="">All Types</option>
          {types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
        <select className={select} value={siteId} onChange={(e) => setSiteId(e.target.value)}>
          <option value="">All Sites</option>
          {sites.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </div>

      <KPIStrip>
        <KPICard label="Runtime Hours" value={data.total_runtime_hours} />
        <KPICard label="Idle Hours" value={data.total_idle_hours} />
        <KPICard label="Rental Days" value={data.total_rental_days} />
        <KPICard label="Idle %" value={`${data.idle_percentage}%`} />
        <KPICard label="Fleet Util" value={`${data.fleet_utilization_pct}%`} accent="yellow" />
        <KPICard label="Sites" value={data.site_usage.length} />
      </KPIStrip>

      <div className="grid gap-10 lg:grid-cols-2">
        <ChartCard title="Engine hour trend">
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data.engine_hour_trends}>
                <CartesianGrid vertical={false} stroke="#e8e8e4" />
                <XAxis dataKey="period" tick={{ fontSize: 11, fill: '#5c5c5c' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#5c5c5c' }} axisLine={false} tickLine={false} width={32} />
                <Tooltip />
                <Line type="monotone" dataKey="engine_hours" stroke="#0d0d0d" strokeWidth={2} dot={false} />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
        <ChartCard title="Site usage">
          <div className="h-56">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data.site_usage as any[]} barCategoryGap="30%">
                <CartesianGrid vertical={false} stroke="#e8e8e4" />
                <XAxis dataKey="site_id" tick={{ fontSize: 11, fill: '#5c5c5c' }} axisLine={false} tickLine={false} />
                <YAxis tick={{ fontSize: 11, fill: '#5c5c5c' }} axisLine={false} tickLine={false} width={32} />
                <Tooltip />
                <Bar dataKey="engine" fill="#ffcd11" name="Engine" />
                <Bar dataKey="idle" fill="#5c5c5c" name="Idle" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </div>

      <div className="grid gap-10 lg:grid-cols-2">
        <div>
          <h3 className="section-label">Downtime indicators</h3>
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-cat-black text-[10px] uppercase tracking-[0.12em] text-cat-gray">
                <th className="pb-2 text-left font-semibold">Equipment</th>
                <th className="pb-2 text-left font-semibold">Idle</th>
                <th className="pb-2 text-left font-semibold">Engine</th>
                <th className="pb-2 text-left font-semibold">Flag</th>
              </tr>
            </thead>
            <tbody>
              {data.downtime_indicators.map((d: any, i) => (
                <tr key={i} className="border-b border-cat-muted">
                  <td className="py-2 font-semibold">{d.equipment_id}</td>
                  <td className="py-2 tabular-nums">{d.idle_hours}</td>
                  <td className="py-2 tabular-nums">{d.engine_hours}</td>
                  <td className="py-2 text-xs uppercase">{d.indicator}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div>
          <h3 className="section-label">Operator usage</h3>
          <table className="min-w-full text-sm">
            <thead>
              <tr className="border-b border-cat-black text-[10px] uppercase tracking-[0.12em] text-cat-gray">
                <th className="pb-2 text-left font-semibold">Operator</th>
                <th className="pb-2 text-left font-semibold">Assignments</th>
                <th className="pb-2 text-left font-semibold">Engine hrs</th>
              </tr>
            </thead>
            <tbody>
              {data.operator_usage.map((o: any) => (
                <tr key={o.operator_id} className="border-b border-cat-muted">
                  <td className="py-2">{o.operator_id}</td>
                  <td className="py-2 tabular-nums">{o.count}</td>
                  <td className="py-2 tabular-nums">{o.engine}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
