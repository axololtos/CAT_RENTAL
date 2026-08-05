"""Domain models and Pydantic schemas."""

from __future__ import annotations

from datetime import date, datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


class EquipmentStatus(str, Enum):
    AVAILABLE = "AVAILABLE"
    RENTED = "RENTED"
    DUE_SOON = "DUE SOON"
    OVERDUE = "OVERDUE"
    UNDER_UTILIZED = "UNDER-UTILIZED"
    ANOMALY = "ANOMALY"


class UtilizationCategory(str, Enum):
    LOW = "LOW"
    MODERATE = "MODERATE"
    GOOD = "GOOD"
    HIGH = "HIGH"
    UNKNOWN = "UNKNOWN"


class AlertSeverity(str, Enum):
    INFO = "INFO"
    REMINDER = "REMINDER"
    WARNING = "WARNING"
    URGENT = "URGENT"
    OVERDUE = "OVERDUE"
    CRITICAL = "CRITICAL"


class AlertCategory(str, Enum):
    OVERDUE = "OVERDUE"
    RETURN_APPROACHING = "RETURN APPROACHING"
    ANOMALY = "ANOMALY"
    LOW_UTILIZATION = "LOW UTILIZATION"
    DATA_SOURCE_ERROR = "DATA SOURCE ERROR"


class AnomalySource(str, Enum):
    RULE = "RULE"
    ML = "ML"


# ---------------------------------------------------------------------------
# Core domain
# ---------------------------------------------------------------------------

class EquipmentRecord(BaseModel):
    equipment_id: str
    type: str
    site_id: Optional[str] = None
    check_in_date: Optional[date] = None  # Leaves company (rented out)
    check_out_date: Optional[date] = None  # Returns to company
    engine_hours_per_day: Optional[float] = None
    idle_hours_per_day: Optional[float] = None
    rental_days: Optional[int] = None
    last_operator_id: Optional[str] = None
    expected_return_date: Optional[date] = None

    # Derived
    status: Optional[EquipmentStatus] = None
    utilization_pct: Optional[float] = None
    utilization_category: Optional[UtilizationCategory] = None
    is_active_rental: bool = False
    anomaly_flags: list[str] = Field(default_factory=list)
    ml_anomaly_score: Optional[float] = None
    is_ml_anomaly: bool = False


class DataQualityIssue(BaseModel):
    row_index: Optional[int] = None
    equipment_id: Optional[str] = None
    field: Optional[str] = None
    severity: str = "WARNING"
    message: str


class DataIngestionResult(BaseModel):
    records: list[EquipmentRecord]
    issues: list[DataQualityIssue]
    source: str
    loaded_at: datetime
    row_count: int
    valid_count: int
    skipped_count: int


class Alert(BaseModel):
    id: str
    equipment_id: Optional[str] = None
    category: AlertCategory
    severity: AlertSeverity
    title: str
    message: str
    detected_at: datetime
    read: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class Anomaly(BaseModel):
    id: str
    equipment_id: str
    source: AnomalySource
    severity: AlertSeverity
    reason: str
    detected_at: datetime
    relevant_values: dict[str, Any] = Field(default_factory=dict)
    anomaly_score: Optional[float] = None  # ML only


class ForecastItem(BaseModel):
    equipment_type: str
    site_id: str
    period_start: date
    period_end: date
    predicted_demand: float
    demand_level: str  # LOW / MEDIUM / HIGH
    confidence: Optional[str] = None
    model_name: Optional[str] = None


class ForecastResult(BaseModel):
    items: list[ForecastItem]
    model_name: str
    mae: Optional[float] = None
    rmse: Optional[float] = None
    sufficient_data: bool
    message: str
    demo_mode: bool = False
    horizon_days: int
    generated_at: datetime


class Recommendation(BaseModel):
    id: str
    equipment_id: Optional[str] = None
    site_id: Optional[str] = None
    equipment_type: Optional[str] = None
    priority: str
    message: str
    rationale: str
    created_at: datetime


class RentalTransaction(BaseModel):
    id: str
    equipment_id: str
    transaction_type: str  # CHECK_IN | CHECK_OUT
    site_id: Optional[str] = None
    operator_id: Optional[str] = None
    transaction_date: date
    expected_return_date: Optional[date] = None
    engine_hours: Optional[float] = None
    condition_notes: Optional[str] = None
    created_at: datetime


# ---------------------------------------------------------------------------
# API request / response
# ---------------------------------------------------------------------------

class CheckInRequest(BaseModel):
    equipment_id: str = Field(..., min_length=1)
    site_id: str = Field(..., min_length=1)
    operator_id: str = Field(..., min_length=1)
    check_in_date: date  # Date equipment leaves company
    expected_return_date: date


class CheckOutRequest(BaseModel):
    equipment_id: str = Field(..., min_length=1)
    actual_return_date: date  # Date equipment returns to company
    final_engine_hours: Optional[float] = None
    condition_notes: Optional[str] = None


class AppendEquipmentRequest(BaseModel):
    """User query-form submission — appends into the live fleet dataset."""

    equipment_id: str = Field(..., min_length=1)
    type: str = Field(..., min_length=1)
    site_id: Optional[str] = None
    check_in_date: Optional[date] = None
    check_out_date: Optional[date] = None
    engine_hours_per_day: Optional[float] = None
    idle_hours_per_day: Optional[float] = None
    rental_days: Optional[int] = None
    last_operator_id: Optional[str] = None
    expected_return_date: Optional[date] = None


class SettingsUpdate(BaseModel):
    data_source_type: Optional[str] = None
    cloud_csv_url: Optional[str] = None
    refresh_interval_seconds: Optional[int] = None
    util_low_max: Optional[float] = None
    util_moderate_max: Optional[float] = None
    util_good_max: Optional[float] = None
    idle_hours_anomaly_threshold: Optional[float] = None
    due_soon_days: Optional[int] = None
    forecast_horizon_days: Optional[int] = None
    use_demo_forecast_data: Optional[bool] = None


class DashboardResponse(BaseModel):
    total_equipment: int
    currently_rented: int
    available: int
    overdue: int
    under_utilized: int
    anomalies: int
    fleet_utilization_pct: float
    total_engine_hours: float
    total_idle_hours: float
    average_rental_duration: float
    active_sites: int
    status_breakdown: dict[str, int]
    type_breakdown: dict[str, int]
    site_utilization: dict[str, float]
    engine_vs_idle: list[dict[str, Any]]
    rental_activity_trend: list[dict[str, Any]]
    site_usage: list[dict[str, Any]]
    recent_alerts: list[Alert]
    last_updated: datetime
    data_source: str
    data_warnings: list[str] = Field(default_factory=list)


class EquipmentListResponse(BaseModel):
    items: list[EquipmentRecord]
    total: int
    last_updated: datetime


class AnalyticsResponse(BaseModel):
    total_runtime_hours: float
    total_idle_hours: float
    total_rental_days: int
    downtime_indicators: list[dict[str, Any]]
    site_usage: list[dict[str, Any]]
    type_usage: list[dict[str, Any]]
    operator_usage: list[dict[str, Any]]
    utilization_by_equipment: list[dict[str, Any]]
    engine_hour_trends: list[dict[str, Any]]
    rental_duration_trends: list[dict[str, Any]]
    idle_percentage: float
    fleet_utilization_pct: float


class AnomalySummaryResponse(BaseModel):
    total: int
    critical: int
    warning: int
    potential_ml: int
    anomalies: list[Anomaly]
    by_severity: dict[str, int]
    by_source: dict[str, int]


class HealthResponse(BaseModel):
    status: str
    data_source: str
    last_updated: Optional[datetime] = None
    record_count: int = 0
    warnings: list[str] = Field(default_factory=list)
