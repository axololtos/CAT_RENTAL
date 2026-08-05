"""Analytics and dashboard aggregation — all values derived from loaded data."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Optional

from models.schemas import (
    Alert,
    AnalyticsResponse,
    Anomaly,
    DashboardResponse,
    EquipmentRecord,
    EquipmentStatus,
)
from utils.status import calculate_utilization, enrich_record, is_active_rental


def enrich_fleet(
    records: list[EquipmentRecord],
    anomaly_equipment_ids: set[str],
) -> list[EquipmentRecord]:
    enriched = []
    for r in records:
        copy = r.model_copy(deep=True)
        has_anom = copy.equipment_id in anomaly_equipment_ids or copy.is_ml_anomaly
        if has_anom and "anomaly" not in copy.anomaly_flags:
            copy.anomaly_flags = list(copy.anomaly_flags) + ["detected"]
        enrich_record(copy, has_anomaly=has_anom)
        enriched.append(copy)
    return enriched


def build_dashboard(
    records: list[EquipmentRecord],
    alerts: list[Alert],
    anomaly_count: int,
    last_updated: datetime,
    data_source: str,
    warnings: list[str],
) -> DashboardResponse:
    total = len(records)
    rented = sum(1 for r in records if is_active_rental(r))
    available = sum(1 for r in records if r.status == EquipmentStatus.AVAILABLE)
    overdue = sum(1 for r in records if r.status == EquipmentStatus.OVERDUE)
    # Count under-utilized by utilization threshold (status may show ANOMALY with higher priority)
    under = 0
    for r in records:
        util = calculate_utilization(r.engine_hours_per_day, r.idle_hours_per_day)
        if util is not None and util < 30.0:
            under += 1
        elif r.status == EquipmentStatus.UNDER_UTILIZED:
            under += 1

    utils = [
        calculate_utilization(r.engine_hours_per_day, r.idle_hours_per_day)
        for r in records
    ]
    valid_utils = [u for u in utils if u is not None]
    fleet_util = round(sum(valid_utils) / len(valid_utils), 2) if valid_utils else 0.0

    total_engine = sum(r.engine_hours_per_day or 0 for r in records)
    total_idle = sum(r.idle_hours_per_day or 0 for r in records)

    durations = [r.rental_days for r in records if r.rental_days is not None]
    avg_duration = round(sum(durations) / len(durations), 2) if durations else 0.0

    sites = {r.site_id for r in records if r.site_id}

    status_breakdown: dict[str, int] = defaultdict(int)
    type_breakdown: dict[str, int] = defaultdict(int)
    for r in records:
        status_breakdown[r.status.value if r.status else "UNKNOWN"] += 1
        type_breakdown[r.type] += 1

    # Site utilization
    site_engine: dict[str, float] = defaultdict(float)
    site_idle: dict[str, float] = defaultdict(float)
    for r in records:
        if not r.site_id:
            continue
        site_engine[r.site_id] += r.engine_hours_per_day or 0
        site_idle[r.site_id] += r.idle_hours_per_day or 0
    site_utilization = {}
    for site in site_engine:
        site_utilization[site] = calculate_utilization(site_engine[site], site_idle[site]) or 0.0

    engine_vs_idle = [
        {
            "equipment_id": r.equipment_id,
            "type": r.type,
            "engine_hours": r.engine_hours_per_day or 0,
            "idle_hours": r.idle_hours_per_day or 0,
        }
        for r in records
    ]

    # Rental activity trend by check-in month
    trend: dict[str, int] = defaultdict(int)
    for r in records:
        if r.check_in_date:
            key = r.check_in_date.strftime("%Y-%m")
            trend[key] += 1
    rental_activity_trend = [
        {"period": k, "rentals": v} for k, v in sorted(trend.items())
    ]

    site_usage = [
        {
            "site_id": site,
            "equipment_count": sum(1 for r in records if r.site_id == site),
            "engine_hours": site_engine.get(site, 0),
            "idle_hours": site_idle.get(site, 0),
            "utilization_pct": site_utilization.get(site, 0),
        }
        for site in sorted(sites)
    ]

    return DashboardResponse(
        total_equipment=total,
        currently_rented=rented,
        available=available,
        overdue=overdue,
        under_utilized=under,
        anomalies=anomaly_count,
        fleet_utilization_pct=fleet_util,
        total_engine_hours=round(total_engine, 2),
        total_idle_hours=round(total_idle, 2),
        average_rental_duration=avg_duration,
        active_sites=len(sites),
        status_breakdown=dict(status_breakdown),
        type_breakdown=dict(type_breakdown),
        site_utilization=site_utilization,
        engine_vs_idle=engine_vs_idle,
        rental_activity_trend=rental_activity_trend,
        site_usage=site_usage,
        recent_alerts=alerts[:8],
        last_updated=last_updated,
        data_source=data_source,
        data_warnings=warnings,
    )


def build_analytics(
    records: list[EquipmentRecord],
    equipment_id: Optional[str] = None,
    equipment_type: Optional[str] = None,
    site_id: Optional[str] = None,
) -> AnalyticsResponse:
    filtered = records
    if equipment_id:
        filtered = [r for r in filtered if r.equipment_id == equipment_id]
    if equipment_type:
        filtered = [r for r in filtered if r.type.lower() == equipment_type.lower()]
    if site_id:
        filtered = [r for r in filtered if r.site_id and r.site_id.lower() == site_id.lower()]

    total_runtime = sum(r.engine_hours_per_day or 0 for r in filtered)
    total_idle = sum(r.idle_hours_per_day or 0 for r in filtered)
    total_days = sum(r.rental_days or 0 for r in filtered)
    idle_pct = (
        round(total_idle / (total_runtime + total_idle) * 100, 2)
        if (total_runtime + total_idle) > 0
        else 0.0
    )
    utils = [
        calculate_utilization(r.engine_hours_per_day, r.idle_hours_per_day) for r in filtered
    ]
    valid = [u for u in utils if u is not None]
    fleet_util = round(sum(valid) / len(valid), 2) if valid else 0.0

    downtime = [
        {
            "equipment_id": r.equipment_id,
            "type": r.type,
            "idle_hours": r.idle_hours_per_day or 0,
            "engine_hours": r.engine_hours_per_day or 0,
            "indicator": "HIGH_IDLE" if (r.idle_hours_per_day or 0) >= 8 else "INACTIVE"
            if (r.engine_hours_per_day or 0) == 0
            else "NORMAL",
        }
        for r in filtered
        if (r.idle_hours_per_day or 0) >= 8 or (r.engine_hours_per_day or 0) == 0
    ]

    site_map: dict[str, dict] = defaultdict(lambda: {"count": 0, "engine": 0.0, "idle": 0.0})
    type_map: dict[str, dict] = defaultdict(lambda: {"count": 0, "engine": 0.0, "idle": 0.0, "days": 0})
    op_map: dict[str, dict] = defaultdict(lambda: {"count": 0, "engine": 0.0})

    for r in filtered:
        if r.site_id:
            site_map[r.site_id]["count"] += 1
            site_map[r.site_id]["engine"] += r.engine_hours_per_day or 0
            site_map[r.site_id]["idle"] += r.idle_hours_per_day or 0
        type_map[r.type]["count"] += 1
        type_map[r.type]["engine"] += r.engine_hours_per_day or 0
        type_map[r.type]["idle"] += r.idle_hours_per_day or 0
        type_map[r.type]["days"] += r.rental_days or 0
        if r.last_operator_id:
            op_map[r.last_operator_id]["count"] += 1
            op_map[r.last_operator_id]["engine"] += r.engine_hours_per_day or 0

    util_by_eq = [
        {
            "equipment_id": r.equipment_id,
            "type": r.type,
            "site_id": r.site_id,
            "utilization_pct": calculate_utilization(r.engine_hours_per_day, r.idle_hours_per_day),
            "engine_hours": r.engine_hours_per_day,
            "idle_hours": r.idle_hours_per_day,
            "category": r.utilization_category.value if r.utilization_category else None,
        }
        for r in filtered
    ]

    month_engine: dict[str, float] = defaultdict(float)
    month_days: dict[str, float] = defaultdict(float)
    month_count: dict[str, int] = defaultdict(int)
    for r in filtered:
        if r.check_in_date:
            key = r.check_in_date.strftime("%Y-%m")
            month_engine[key] += r.engine_hours_per_day or 0
            month_days[key] += r.rental_days or 0
            month_count[key] += 1

    return AnalyticsResponse(
        total_runtime_hours=round(total_runtime, 2),
        total_idle_hours=round(total_idle, 2),
        total_rental_days=total_days,
        downtime_indicators=downtime,
        site_usage=[
            {"site_id": k, **v, "utilization_pct": calculate_utilization(v["engine"], v["idle"])}
            for k, v in sorted(site_map.items())
        ],
        type_usage=[{"type": k, **v} for k, v in sorted(type_map.items())],
        operator_usage=[{"operator_id": k, **v} for k, v in sorted(op_map.items())],
        utilization_by_equipment=util_by_eq,
        engine_hour_trends=[
            {"period": k, "engine_hours": round(v, 2)} for k, v in sorted(month_engine.items())
        ],
        rental_duration_trends=[
            {
                "period": k,
                "avg_rental_days": round(month_days[k] / month_count[k], 2) if month_count[k] else 0,
                "rentals": month_count[k],
            }
            for k in sorted(month_days.keys())
        ],
        idle_percentage=idle_pct,
        fleet_utilization_pct=fleet_util,
    )
