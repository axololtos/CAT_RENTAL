const API_BASE = import.meta.env.VITE_API_BASE || '';

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options?.headers || {}) },
    ...options,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail || JSON.stringify(body);
    } catch {
      /* ignore */
    }
    throw new Error(typeof detail === 'string' ? detail : JSON.stringify(detail));
  }
  if (res.headers.get('content-type')?.includes('text/csv')) {
    return (await res.text()) as T;
  }
  return res.json();
}

export const api = {
  health: () => request('/api/health'),
  refresh: (retrain = false) =>
    request<{ ok: boolean; last_updated?: string }>(`/api/refresh?retrain_forecast=${retrain}`, {
      method: 'POST',
    }),
  dashboard: () => request<import('../types').DashboardData>('/api/dashboard'),
  equipment: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<{ items: import('../types').Equipment[]; total: number; last_updated: string }>(
      `/api/equipment${qs}`,
    );
  },
  equipmentDetail: (id: string) => request(`/api/equipment/${encodeURIComponent(id)}`),
  analytics: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<import('../types').AnalyticsData>(`/api/analytics${qs}`);
  },
  alerts: () => request<import('../types').Alert[]>('/api/alerts'),
  anomalies: () => request<import('../types').AnomalySummary>('/api/anomalies'),
  forecast: (horizon?: number) =>
    request<import('../types').ForecastResult>(
      horizon ? `/api/forecast?horizon_days=${horizon}` : '/api/forecast',
    ),
  recommendations: () => request<import('../types').Recommendation[]>('/api/recommendations'),
  rentals: (equipmentId?: string) =>
    request<import('../types').RentalTransaction[]>(
      equipmentId ? `/api/rentals?equipment_id=${encodeURIComponent(equipmentId)}` : '/api/rentals',
    ),
  checkIn: (body: Record<string, unknown>) =>
    request('/api/check-in', { method: 'POST', body: JSON.stringify(body) }),
  checkOut: (body: Record<string, unknown>) =>
    request('/api/check-out', { method: 'POST', body: JSON.stringify(body) }),
  appendEquipment: (body: Record<string, unknown>) =>
    request('/api/equipment/append', { method: 'POST', body: JSON.stringify(body) }),
  notifications: (params?: Record<string, string>) => {
    const qs = params ? '?' + new URLSearchParams(params).toString() : '';
    return request<import('../types').Alert[]>(`/api/notifications${qs}`);
  },
  markRead: (id: string, read = true) =>
    request(`/api/notifications/${encodeURIComponent(id)}/read?read=${read}`, { method: 'POST' }),
  settings: () => request<import('../types').AppSettings>('/api/settings'),
  updateSettings: (body: Partial<import('../types').AppSettings>) =>
    request<import('../types').AppSettings>('/api/settings', {
      method: 'PUT',
      body: JSON.stringify(body),
    }),
  dataQuality: () => request('/api/data-quality'),
  exportReport: (reportType: string) =>
    `${API_BASE}/api/reports/export?report_type=${encodeURIComponent(reportType)}`,
  hybridDashboard: () => request<import('../types').HybridDashboard>('/api/hybrid/dashboard'),
  hybridArchitecture: () => request<import('../types').HybridTopology>('/api/hybrid/architecture'),
  hybridContracts: () => request<import('../types').HybridContract[]>('/api/hybrid/contracts'),
  hybridLiveState: () => request<import('../types').HybridLiveState[]>('/api/hybrid/live-state'),
  hybridTelemetry: () => request('/api/hybrid/telemetry'),
};
