interface FilterBarProps {
  search: string;
  onSearch: (v: string) => void;
  type: string;
  onType: (v: string) => void;
  site: string;
  onSite: (v: string) => void;
  status: string;
  onStatus: (v: string) => void;
  utilization: string;
  onUtilization: (v: string) => void;
  anomaly: string;
  onAnomaly: (v: string) => void;
  types: string[];
  sites: string[];
}

const STATUSES = ['', 'AVAILABLE', 'RENTED', 'DUE SOON', 'OVERDUE', 'UNDER-UTILIZED', 'ANOMALY'];
const UTILS = ['', 'LOW', 'MODERATE', 'GOOD', 'HIGH'];
const select =
  'min-w-[120px] border-0 border-b border-cat-muted bg-transparent py-2 text-sm outline-none focus:border-cat-yellow';

export function FilterBar(props: FilterBarProps) {
  return (
    <div className="flex flex-wrap items-end gap-x-5 gap-y-3">
      <label className="flex min-w-[200px] flex-1 flex-col gap-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-cat-gray">
        Search
        <input
          className="border-0 border-b border-cat-muted bg-transparent py-2 text-sm outline-none focus:border-cat-yellow"
          value={props.search}
          onChange={(e) => props.onSearch(e.target.value)}
          placeholder="ID, type, site…"
        />
      </label>
      <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-cat-gray">
        Type
        <select className={select} value={props.type} onChange={(e) => props.onType(e.target.value)}>
          <option value="">All</option>
          {props.types.map((t) => (
            <option key={t} value={t}>
              {t}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-cat-gray">
        Site
        <select className={select} value={props.site} onChange={(e) => props.onSite(e.target.value)}>
          <option value="">All</option>
          {props.sites.map((s) => (
            <option key={s} value={s}>
              {s}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-cat-gray">
        Status
        <select className={select} value={props.status} onChange={(e) => props.onStatus(e.target.value)}>
          {STATUSES.map((s) => (
            <option key={s || 'all'} value={s}>
              {s || 'All'}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-cat-gray">
        Utilization
        <select
          className={select}
          value={props.utilization}
          onChange={(e) => props.onUtilization(e.target.value)}
        >
          {UTILS.map((u) => (
            <option key={u || 'all'} value={u}>
              {u || 'All'}
            </option>
          ))}
        </select>
      </label>
      <label className="flex flex-col gap-1 text-[10px] font-semibold uppercase tracking-[0.12em] text-cat-gray">
        Anomaly
        <select className={select} value={props.anomaly} onChange={(e) => props.onAnomaly(e.target.value)}>
          <option value="">All</option>
          <option value="yes">Has anomaly</option>
          <option value="no">No anomaly</option>
        </select>
      </label>
    </div>
  );
}
