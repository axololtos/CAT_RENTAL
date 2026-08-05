export type EquipmentStatus =
  | 'AVAILABLE'
  | 'RENTED'
  | 'DUE SOON'
  | 'OVERDUE'
  | 'UNDER-UTILIZED'
  | 'ANOMALY';

export type UtilizationCategory = 'LOW' | 'MODERATE' | 'GOOD' | 'HIGH' | 'UNKNOWN';

export interface Equipment {
  equipment_id: string;
  type: string;
  site_id: string | null;
  check_in_date: string | null;
  check_out_date: string | null;
  engine_hours_per_day: number | null;
  idle_hours_per_day: number | null;
  rental_days: number | null;
  last_operator_id: string | null;
  expected_return_date: string | null;
  status: EquipmentStatus | null;
  utilization_pct: number | null;
  utilization_category: UtilizationCategory | null;
  is_active_rental: boolean;
  anomaly_flags: string[];
  ml_anomaly_score: number | null;
  is_ml_anomaly: boolean;
}

export interface Alert {
  id: string;
  equipment_id: string | null;
  category: string;
  severity: string;
  title: string;
  message: string;
  detected_at: string;
  read: boolean;
  metadata: Record<string, unknown>;
}

export interface Anomaly {
  id: string;
  equipment_id: string;
  source: 'RULE' | 'ML';
  severity: string;
  reason: string;
  detected_at: string;
  relevant_values: Record<string, unknown>;
  anomaly_score: number | null;
}

export interface ForecastItem {
  equipment_type: string;
  site_id: string;
  period_start: string;
  period_end: string;
  predicted_demand: number;
  demand_level: string;
  confidence: string | null;
  model_name: string | null;
}

export interface ForecastResult {
  items: ForecastItem[];
  model_name: string;
  mae: number | null;
  rmse: number | null;
  sufficient_data: boolean;
  message: string;
  demo_mode: boolean;
  horizon_days: number;
  generated_at: string;
}

export interface Recommendation {
  id: string;
  equipment_id: string | null;
  site_id: string | null;
  equipment_type: string | null;
  priority: string;
  message: string;
  rationale: string;
  created_at: string;
}

export interface RentalTransaction {
  id: string;
  equipment_id: string;
  transaction_type: 'CHECK_IN' | 'CHECK_OUT' | string;
  site_id: string | null;
  operator_id: string | null;
  transaction_date: string;
  expected_return_date: string | null;
  engine_hours: number | null;
  condition_notes: string | null;
  created_at: string;
}

export interface DashboardData {
  total_equipment: number;
  currently_rented: number;
  available: number;
  overdue: number;
  under_utilized: number;
  anomalies: number;
  fleet_utilization_pct: number;
  total_engine_hours: number;
  total_idle_hours: number;
  average_rental_duration: number;
  active_sites: number;
  status_breakdown: Record<string, number>;
  type_breakdown: Record<string, number>;
  site_utilization: Record<string, number>;
  engine_vs_idle: Array<{
    equipment_id: string;
    type: string;
    engine_hours: number;
    idle_hours: number;
  }>;
  rental_activity_trend: Array<{ period: string; rentals: number }>;
  site_usage: Array<{
    site_id: string;
    equipment_count: number;
    engine_hours: number;
    idle_hours: number;
    utilization_pct: number;
  }>;
  recent_alerts: Alert[];
  last_updated: string;
  data_source: string;
  data_warnings: string[];
}

export interface AnalyticsData {
  total_runtime_hours: number;
  total_idle_hours: number;
  total_rental_days: number;
  downtime_indicators: Array<Record<string, unknown>>;
  site_usage: Array<Record<string, unknown>>;
  type_usage: Array<Record<string, unknown>>;
  operator_usage: Array<Record<string, unknown>>;
  utilization_by_equipment: Array<Record<string, unknown>>;
  engine_hour_trends: Array<{ period: string; engine_hours: number }>;
  rental_duration_trends: Array<{ period: string; avg_rental_days: number; rentals: number }>;
  idle_percentage: number;
  fleet_utilization_pct: number;
}

export interface AppSettings {
  data_source_type: string;
  cloud_csv_url: string;
  refresh_interval_seconds: number;
  util_low_max: number;
  util_moderate_max: number;
  util_good_max: number;
  idle_hours_anomaly_threshold: number;
  due_soon_days: number;
  forecast_horizon_days: number;
  use_demo_forecast_data: boolean;
  min_forecast_records: number;
}

export interface AnomalySummary {
  total: number;
  critical: number;
  warning: number;
  potential_ml: number;
  anomalies: Anomaly[];
  by_severity: Record<string, number>;
  by_source: Record<string, number>;
}

export interface HybridContract {
  equipment_id: string;
  equipment_type: string;
  site_id: string | null;
  dispatch_date: string | null;
  return_date: string | null;
  check_in_date: string | null;
  check_out_date: string | null;
  expected_return_date: string | null;
  rental_days: number | null;
  status: string;
  last_operator_id: string | null;
}

export interface HybridLiveState {
  equipment_id: string;
  equipment_type: string;
  last_operator_id: string | null;
  site_id: string | null;
  lat: number;
  lon: number;
  fuel_pct: number;
  engine_hours: number;
  idle_hours: number;
  engine_hours_total: number;
  idle_hours_total: number;
  utilization_pct: number | null;
  anomaly_status: string;
  anomaly_codes: string[];
  contract_status: string;
  gateway_id: string;
  last_updated: string;
  edge_online: boolean;
}

export interface HybridArchAnomaly {
  id: string;
  equipment_id: string;
  rule: string;
  severity: string;
  title: string;
  reason: string;
  action: string;
  layer: string;
  detected_at: string;
  relevant_values: Record<string, unknown>;
}

export interface HybridComponent {
  id: string;
  name: string;
  status: string;
  layer: string;
  detail?: string;
}

export interface HybridTopology {
  architecture: string;
  updated_at: string;
  edge: HybridComponent[];
  cloud: HybridComponent[];
  data_flows: Array<{ from: string; to: string; protocol: string; note: string }>;
  prototype_note: string;
}

export interface HybridDashboard {
  kpis: {
    fleet_size: number;
    active_contracts: number;
    returned_contracts: number;
    live_assets_online: number;
    critical_anomalies: number;
    under_utilized: number;
    unassigned_usage: number;
    overdue_alerts: number;
    return_reminders: number;
    avg_fuel_pct: number;
    avg_utilization_pct: number;
  };
  contracts: HybridContract[];
  live_state: HybridLiveState[];
  telemetry: unknown[];
  architecture_anomalies: HybridArchAnomaly[];
  overdue_engine: Array<{
    equipment_id: string;
    severity: string;
    remaining_days: number;
    due_date: string;
    message: string;
  }>;
  demand_forecast_preview: Array<{
    equipment_type: string;
    site_id: string;
    predicted_demand: number;
    demand_level: string;
  }>;
  topology: HybridTopology;
  workflow: {
    dispatch: { architecture_name: string; description: string };
    return: { architecture_name: string; description: string };
    csv_mapping: Record<string, string>;
  };
  generated_at: string;
}
