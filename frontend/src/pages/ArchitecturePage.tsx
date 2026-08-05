import { useEffect, useState } from 'react';
import { api } from '../services/api';
import { useData } from '../hooks/useData';
import type { HybridTopology } from '../types';
import { LoadingState, ErrorState } from '../components/States';

export function ArchitecturePage() {
  const { tick } = useData();
  const [data, setData] = useState<HybridTopology | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    setLoading(true);
    api
      .hybridArchitecture()
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

  return (
    <div className="page">
      <div>
        <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-cat-gray">
          Solution Design
        </p>
        <h2 className="page-title">Hybrid-Cloud Architecture</h2>
        <p className="page-sub">{data.architecture}</p>
      </div>

      {/* Visual topology */}
      <div className="grid gap-6 lg:grid-cols-2">
        <LayerPanel title="On-Site / Edge Layer" accent="yellow" items={data.edge} />
        <LayerPanel title="AWS Cloud Backend" accent="black" items={data.cloud} />
      </div>

      <div>
        <h3 className="section-label">Data flows</h3>
        <div className="space-y-0">
          {data.data_flows.map((f, i) => (
            <div
              key={i}
              className="grid gap-2 border-b border-cat-muted py-3 text-sm sm:grid-cols-[1fr_auto_1fr] sm:items-center"
            >
              <span className="font-semibold">{f.from}</span>
              <span className="text-[10px] font-bold uppercase tracking-wide text-cat-gray">
                {f.protocol} →
              </span>
              <span>
                <span className="font-semibold">{f.to}</span>
                <span className="mt-0.5 block text-xs text-cat-gray">{f.note}</span>
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="grid gap-8 lg:grid-cols-3">
        <InfoBlock
          title="Contracts vs Telemetry"
          body="RentalContracts hold short-term rental metadata. EquipmentLiveState holds continuous machine telemetry. Separating them preserves data integrity."
        />
        <InfoBlock
          title="Offline resilience"
          body="Greengrass Stream Manager buffers telemetry in SQLite during cellular dropouts, then auto-syncs to IoT Core over MQTT/TLS."
        />
        <InfoBlock
          title="Cost-efficient lake"
          body="Firehose writes compressed Parquet to S3 (year/month/site partitions). Athena and SageMaker read the lake without expensive hot-DB writes."
        />
      </div>

      <div>
        <h3 className="section-label">Operational engines</h3>
        <div className="grid gap-6 md:grid-cols-3">
          <InfoBlock
            title="Anomaly rules"
            body="UNASSIGNED_USAGE · UNDER_UTILIZED (idle/engine > 0.60) · MISSING_OPERATOR — IoT Rule → Lambda → SNS + dashboard."
          />
          <InfoBlock
            title="Overdue scheduler"
            body="EventBridge nightly job: remaining days = due date − today. ≤2 days → return reminder. Past due → CRITICAL_OVERDUE + SNS."
          />
          <InfoBlock
            title="Demand forecast"
            body="Weekly SageMaker/XGBoost batch on historical lake features — 14-day site × type demand map for pre-positioning."
          />
        </div>
      </div>

      <p className="text-[11px] text-cat-gray">{data.prototype_note}</p>
    </div>
  );
}

function LayerPanel({
  title,
  accent,
  items,
}: {
  title: string;
  accent: 'yellow' | 'black';
  items: HybridTopology['edge'];
}) {
  return (
    <div>
      <div className={`mb-3 border-l-4 pl-3 ${accent === 'yellow' ? 'border-cat-yellow' : 'border-cat-black'}`}>
        <h3 className="text-sm font-semibold">{title}</h3>
      </div>
      <ul className="space-y-2">
        {items.map((c) => (
          <li key={c.id} className="flex items-start justify-between gap-3 border-b border-cat-muted py-2">
            <div>
              <p className="text-sm font-medium">{c.name}</p>
              {c.detail && <p className="text-[11px] text-cat-gray">{c.detail}</p>}
            </div>
            <span className="shrink-0 text-[10px] font-bold uppercase tracking-wide text-emerald-700">
              {c.status}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

function InfoBlock({ title, body }: { title: string; body: string }) {
  return (
    <div>
      <h4 className="text-sm font-semibold">{title}</h4>
      <p className="mt-1 text-xs leading-relaxed text-cat-gray">{body}</p>
    </div>
  );
}
