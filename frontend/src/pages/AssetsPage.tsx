import { useEffect, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { api } from '../services/api';
import { useData } from '../hooks/useData';
import type { Equipment } from '../types';
import { FilterBar } from '../components/FilterBar';
import { EquipmentTable } from '../components/EquipmentTable';
import { LoadingState, ErrorState } from '../components/States';

export function AssetsPage() {
  const { tick } = useData();
  const navigate = useNavigate();
  const [items, setItems] = useState<Equipment[]>([]);
  const [all, setAll] = useState<Equipment[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');
  const [type, setType] = useState('');
  const [site, setSite] = useState('');
  const [status, setStatus] = useState('');
  const [utilization, setUtilization] = useState('');
  const [anomaly, setAnomaly] = useState('');

  useEffect(() => {
    api.equipment().then((res) => setAll(res.items)).catch((e) => setError(e.message));
  }, [tick]);

  useEffect(() => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (search) params.search = search;
    if (type) params.type = type;
    if (site) params.site = site;
    if (status) params.status = status;
    if (utilization) params.utilization = utilization;
    if (anomaly) params.anomaly = anomaly;
    api
      .equipment(params)
      .then((res) => {
        setItems(res.items);
        setError(null);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [tick, search, type, site, status, utilization, anomaly]);

  const types = useMemo(() => [...new Set(all.map((a) => a.type))].sort(), [all]);
  const sites = useMemo(
    () => [...new Set(all.map((a) => a.site_id).filter(Boolean) as string[])].sort(),
    [all],
  );

  return (
    <div className="page">
      <div>
        <h2 className="page-title">Assets</h2>
        <p className="page-sub">All equipment with live calculated status.</p>
      </div>

      <FilterBar
        search={search}
        onSearch={setSearch}
        type={type}
        onType={setType}
        site={site}
        onSite={setSite}
        status={status}
        onStatus={setStatus}
        utilization={utilization}
        onUtilization={setUtilization}
        anomaly={anomaly}
        onAnomaly={setAnomaly}
        types={types}
        sites={sites}
      />

      {loading && <LoadingState />}
      {error && <ErrorState message={error} />}
      {!loading && !error && (
        <>
          <p className="text-xs text-cat-gray">{items.length} equipment</p>
          <EquipmentTable items={items} onRowClick={(id) => navigate(`/assets/${id}`)} />
        </>
      )}
    </div>
  );
}
