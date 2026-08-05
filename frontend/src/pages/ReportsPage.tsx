import { api } from '../services/api';

const REPORTS = [
  { id: 'utilization', label: 'Fleet Utilization', description: 'Utilization % by equipment' },
  { id: 'rentals', label: 'Rental Activity', description: 'Check-In / Check-Out summary' },
  { id: 'sites', label: 'Site Performance', description: 'Usage by site' },
  { id: 'idle', label: 'Idle Equipment', description: 'High idle-hour units' },
  { id: 'overdue', label: 'Overdue Rentals', description: 'Past expected return' },
  { id: 'anomalies', label: 'Anomalies', description: 'Rule + ML findings' },
  { id: 'forecast', label: 'Demand Forecasts', description: 'Predicted demand export' },
];

export function ReportsPage() {
  return (
    <div className="page max-w-3xl">
      <div>
        <h2 className="page-title">Reports</h2>
        <p className="page-sub">Export CSV summaries from live calculated data.</p>
      </div>

      <div className="divide-y divide-cat-muted border-y border-cat-muted">
        {REPORTS.map((r) => (
          <div key={r.id} className="flex items-center justify-between gap-4 py-4">
            <div>
              <h3 className="text-sm font-semibold">{r.label}</h3>
              <p className="text-xs text-cat-gray">{r.description}</p>
            </div>
            <a href={api.exportReport(r.id)} className="btn-primary shrink-0">
              Export CSV
            </a>
          </div>
        ))}
      </div>
    </div>
  );
}
