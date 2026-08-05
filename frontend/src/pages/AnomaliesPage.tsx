import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from 'recharts';
import { api } from '../services/api';
import { useData } from '../hooks/useData';
import type { AnomalySummary } from '../types';
import { KPICard, KPIStrip } from '../components/KPICard';
import { ChartCard } from '../components/ChartCard';
import { LoadingState, ErrorState } from '../components/States';

const COLORS = ['#0d0d0d', '#ffcd11', '#5c5c5c', '#b91c1c'];

export function AnomaliesPage() {
  const { tick } = useData();
  const [data, setData] = useState<AnomalySummary | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [sourceFilter, setSourceFilter] = useState('');

  useEffect(() => {
    setLoading(true);
    api
      .anomalies()
      .then((d) => {
        setData(d);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tick]);

  if (loading && !data) return <LoadingState />;
  if (error && !data) return <ErrorState message={error} />;
  if (!data) return null;

  const severityData = Object.entries(data.by_severity).map(([name, value]) => ({ name, value }));
  const sourceData = Object.entries(data.by_source).map(([name, value]) => ({ name, value }));
  const filtered = sourceFilter
    ? data.anomalies.filter((a) => a.source === sourceFilter)
    : data.anomalies;

  return (
    <div className="page">
      <div>
        <h2 className="page-title">Anomaly Detection</h2>
        <p className="page-sub">
          Rule-based flags plus Isolation Forest potential anomalies — not confirmed misuse.
        </p>
      </div>

      <KPIStrip>
        <KPICard label="Total" value={data.total} />
        <KPICard label="Critical" value={data.critical} accent="danger" />
        <KPICard label="Warning" value={data.warning} accent="warning" />
        <KPICard label="Potential ML" value={data.potential_ml} accent="yellow" />
        <KPICard label="Rule" value={data.by_source.RULE || 0} />
        <KPICard label="ML" value={data.by_source.ML || 0} />
      </KPIStrip>

      <div className="grid gap-10 lg:grid-cols-2">
        <ChartCard title="By severity">
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <PieChart>
                <Pie data={severityData} dataKey="value" nameKey="name" innerRadius={40} outerRadius={65}>
                  {severityData.map((_, i) => (
                    <Cell key={i} fill={COLORS[i % COLORS.length]} />
                  ))}
                </Pie>
                <Tooltip />
              </PieChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
        <ChartCard title="Rule vs ML">
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={sourceData} barCategoryGap="40%">
                <CartesianGrid vertical={false} stroke="#e8e8e4" />
                <XAxis dataKey="name" tick={{ fontSize: 11, fill: '#5c5c5c' }} axisLine={false} tickLine={false} />
                <YAxis allowDecimals={false} tick={{ fontSize: 11, fill: '#5c5c5c' }} axisLine={false} tickLine={false} width={28} />
                <Tooltip />
                <Bar dataKey="value" fill="#0d0d0d" />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </ChartCard>
      </div>

      <div className="flex gap-4 text-sm">
        {['', 'RULE', 'ML'].map((f) => (
          <button
            key={f || 'all'}
            type="button"
            onClick={() => setSourceFilter(f)}
            className={`pb-1 font-semibold ${sourceFilter === f ? 'border-b-2 border-cat-yellow text-cat-black' : 'text-cat-gray'}`}
          >
            {f === '' ? 'All' : f === 'ML' ? 'Potential (ML)' : 'Rule-Based'}
          </button>
        ))}
      </div>

      <table className="min-w-full text-sm">
        <thead>
          <tr className="border-b border-cat-black text-[10px] uppercase tracking-[0.12em] text-cat-gray">
            <th className="pb-2 text-left font-semibold">Equipment</th>
            <th className="pb-2 text-left font-semibold">Source</th>
            <th className="pb-2 text-left font-semibold">Severity</th>
            <th className="pb-2 text-left font-semibold">Reason</th>
          </tr>
        </thead>
        <tbody>
          {filtered.map((a) => (
            <tr key={a.id} className="border-b border-cat-muted align-top">
              <td className="py-2.5 pr-4 font-semibold">
                <Link className="hover:underline" to={`/assets/${a.equipment_id}`}>
                  {a.equipment_id}
                </Link>
              </td>
              <td className="py-2.5 pr-4">{a.source === 'ML' ? 'Potential' : 'Rule'}</td>
              <td className="py-2.5 pr-4">{a.severity}</td>
              <td className="py-2.5 max-w-xl text-cat-dark">{a.reason}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
