"""FastAPI route handlers."""

from __future__ import annotations

import csv
import io
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse

from models.schemas import (
    AnomalySummaryResponse,
    AppendEquipmentRequest,
    CheckInRequest,
    CheckOutRequest,
    EquipmentListResponse,
    HealthResponse,
    SettingsUpdate,
)
from services import database as db
from services.analytics import build_analytics, build_dashboard
from services.alerts import generate_return_alerts
from services.append import append_equipment
from services.data_store import store
from services.engine import engine
from services.hybrid import build_hybrid_dashboard, system_topology, to_contract, to_live_state, to_telemetry
from services.rentals import perform_check_in, perform_check_out, rental_history

router = APIRouter(prefix="/api")


@router.get("/health", response_model=HealthResponse)
def health():
    return HealthResponse(
        status="ok",
        data_source=store.source,
        last_updated=store.last_updated,
        record_count=len(store.get_records()),
        warnings=store.warnings,
    )


@router.post("/refresh")
def refresh(retrain_forecast: bool = Query(False)):
    """Reload data from configured source. Forecast retrain optional (expensive)."""
    result = engine.refresh(retrain_forecast=retrain_forecast or engine.forecast is None)
    return {"ok": True, **result}


@router.get("/dashboard")
def dashboard():
    records = engine.get_enriched_records()
    alerts = db.list_notifications()[:10]
    return build_dashboard(
        records=records,
        alerts=alerts,
        anomaly_count=len({a.equipment_id for a in engine.anomalies}),
        last_updated=store.last_updated or datetime.utcnow(),
        data_source=store.source,
        warnings=store.warnings,
    )


@router.get("/equipment", response_model=EquipmentListResponse)
def list_equipment(
    search: Optional[str] = None,
    type: Optional[str] = None,
    site: Optional[str] = None,
    status: Optional[str] = None,
    utilization: Optional[str] = None,
    anomaly: Optional[str] = None,
):
    records = engine.get_enriched_records()

    if search:
        q = search.lower()
        records = [
            r
            for r in records
            if q in r.equipment_id.lower()
            or q in (r.type or "").lower()
            or q in (r.site_id or "").lower()
            or q in (r.last_operator_id or "").lower()
        ]
    if type:
        records = [r for r in records if r.type.lower() == type.lower()]
    if site:
        records = [r for r in records if r.site_id and r.site_id.lower() == site.lower()]
    if status:
        records = [r for r in records if r.status and r.status.value.lower() == status.lower()]
    if utilization:
        records = [
            r
            for r in records
            if r.utilization_category and r.utilization_category.value.lower() == utilization.lower()
        ]
    if anomaly:
        flag = anomaly.lower()
        if flag in ("yes", "true", "1", "anomaly"):
            anom_ids = {a.equipment_id for a in engine.anomalies}
            records = [r for r in records if r.equipment_id in anom_ids or r.is_ml_anomaly]
        elif flag in ("no", "false", "0"):
            anom_ids = {a.equipment_id for a in engine.anomalies}
            records = [r for r in records if r.equipment_id not in anom_ids and not r.is_ml_anomaly]

    return EquipmentListResponse(
        items=records,
        total=len(records),
        last_updated=store.last_updated or datetime.utcnow(),
    )


@router.get("/equipment/{equipment_id}")
def get_equipment(equipment_id: str):
    records = engine.get_enriched_records()
    match = next((r for r in records if r.equipment_id == equipment_id), None)
    if not match:
        raise HTTPException(status_code=404, detail="Equipment not found")

    eq_anomalies = [a for a in engine.anomalies if a.equipment_id == equipment_id]
    eq_alerts = [a for a in db.list_notifications(equipment_id=equipment_id)]
    eq_recs = [r for r in engine.recommendations if r.equipment_id == equipment_id]
    history = rental_history(equipment_id)

    return {
        "equipment": match,
        "anomalies": eq_anomalies,
        "alerts": eq_alerts,
        "recommendations": eq_recs,
        "rental_history": history,
        "usage": {
            "engine_hours_per_day": match.engine_hours_per_day,
            "idle_hours_per_day": match.idle_hours_per_day,
            "rental_days": match.rental_days,
            "utilization_pct": match.utilization_pct,
        },
    }


@router.get("/analytics")
def analytics(
    equipment_id: Optional[str] = None,
    equipment_type: Optional[str] = None,
    site_id: Optional[str] = None,
):
    records = engine.get_enriched_records()
    return build_analytics(records, equipment_id, equipment_type, site_id)


@router.get("/alerts")
def alerts(
    category: Optional[str] = None,
    severity: Optional[str] = None,
    equipment_id: Optional[str] = None,
):
    return db.list_notifications(category=category, severity=severity, equipment_id=equipment_id)


@router.get("/anomalies", response_model=AnomalySummaryResponse)
def anomalies():
    items = engine.anomalies
    critical = sum(1 for a in items if a.severity.value == "CRITICAL")
    warning = sum(1 for a in items if a.severity.value == "WARNING")
    potential_ml = sum(1 for a in items if a.source.value == "ML")
    by_severity: dict[str, int] = {}
    by_source: dict[str, int] = {}
    for a in items:
        by_severity[a.severity.value] = by_severity.get(a.severity.value, 0) + 1
        by_source[a.source.value] = by_source.get(a.source.value, 0) + 1
    return AnomalySummaryResponse(
        total=len(items),
        critical=critical,
        warning=warning,
        potential_ml=potential_ml,
        anomalies=items,
        by_severity=by_severity,
        by_source=by_source,
    )


@router.get("/forecast")
def forecast(horizon_days: Optional[int] = None):
    if horizon_days and horizon_days != engine.effective_settings().forecast_horizon_days:
        from ml.forecasting import run_forecast

        return run_forecast(
            engine.get_enriched_records(),
            engine.effective_settings(),
            horizon_days=horizon_days,
        )
    if engine.forecast is None:
        engine.refresh(retrain_forecast=True)
    return engine.forecast


@router.get("/recommendations")
def recommendations():
    return engine.recommendations


@router.get("/rentals")
def rentals(equipment_id: Optional[str] = None):
    return rental_history(equipment_id)


@router.post("/check-in")
def check_in(payload: CheckInRequest):
    """CHECK-IN = equipment leaves the company (rented out)."""
    tx = perform_check_in(payload)
    engine.refresh(retrain_forecast=False)
    return {"ok": True, "transaction": tx, "message": "Equipment checked in (rented out)."}


@router.post("/check-out")
def check_out(payload: CheckOutRequest):
    """CHECK-OUT = equipment returns to the company."""
    tx = perform_check_out(payload)
    engine.refresh(retrain_forecast=False)
    return {"ok": True, "transaction": tx, "message": "Equipment checked out (returned)."}


@router.post("/equipment/append")
def equipment_append(payload: AppendEquipmentRequest):
    """Append a user-submitted equipment row into the live fleet and re-run analytics."""
    record = append_equipment(payload)
    refresh_result = engine.refresh(retrain_forecast=False)
    return {
        "ok": True,
        "message": f"{record.equipment_id} appended — dashboard, anomalies, and alerts updated.",
        "equipment": record,
        "fleet_size": refresh_result.get("loaded"),
        "anomalies": refresh_result.get("anomalies"),
        "alerts": refresh_result.get("alerts"),
    }


@router.get("/notifications")
def notifications(
    category: Optional[str] = None,
    severity: Optional[str] = None,
    equipment_id: Optional[str] = None,
    unread_only: bool = False,
):
    return db.list_notifications(category, severity, equipment_id, unread_only)


@router.post("/notifications/{notification_id}/read")
def mark_read(notification_id: str, read: bool = True):
    ok = db.mark_notification_read(notification_id, read)
    if not ok:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"ok": True}


@router.get("/data-quality")
def data_quality():
    return {
        "issues": store.issues,
        "warnings": store.warnings,
        "source": store.source,
        "last_updated": store.last_updated,
        "last_error": store.last_error,
    }


@router.get("/settings")
def get_settings():
    return engine.get_settings_public()


@router.put("/settings")
def put_settings(payload: SettingsUpdate):
    updated = engine.update_settings(payload.model_dump(exclude_none=True))
    engine.refresh(retrain_forecast=True)
    return engine.get_settings_public()


@router.get("/reports/export")
def export_report(
    report_type: str = Query(
        ...,
        description="utilization|rentals|sites|idle|overdue|anomalies|forecast",
    ),
):
    records = engine.get_enriched_records()
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    if report_type == "utilization":
        writer.writerow(
            ["Equipment ID", "Type", "Site", "Engine Hours", "Idle Hours", "Utilization %", "Status"]
        )
        for r in records:
            writer.writerow(
                [
                    r.equipment_id,
                    r.type,
                    r.site_id or "",
                    r.engine_hours_per_day,
                    r.idle_hours_per_day,
                    r.utilization_pct,
                    r.status.value if r.status else "",
                ]
            )
    elif report_type == "rentals":
        writer.writerow(
            [
                "Equipment ID",
                "Type",
                "Check-In (Rented Out)",
                "Check-Out (Returned)",
                "Expected Return",
                "Rental Days",
                "Site",
                "Operator",
            ]
        )
        for r in records:
            writer.writerow(
                [
                    r.equipment_id,
                    r.type,
                    r.check_in_date,
                    r.check_out_date,
                    r.expected_return_date,
                    r.rental_days,
                    r.site_id or "",
                    r.last_operator_id or "",
                ]
            )
    elif report_type == "sites":
        from services.analytics import build_analytics

        analytics = build_analytics(records)
        writer.writerow(["Site ID", "Count", "Engine Hours", "Idle Hours", "Utilization %"])
        for s in analytics.site_usage:
            writer.writerow(
                [s["site_id"], s["count"], s["engine"], s["idle"], s.get("utilization_pct")]
            )
    elif report_type == "idle":
        writer.writerow(["Equipment ID", "Type", "Idle Hours/Day", "Engine Hours/Day", "Site"])
        for r in records:
            if (r.idle_hours_per_day or 0) >= 6:
                writer.writerow(
                    [r.equipment_id, r.type, r.idle_hours_per_day, r.engine_hours_per_day, r.site_id]
                )
    elif report_type == "overdue":
        writer.writerow(["Equipment ID", "Type", "Site", "Expected Return", "Status"])
        for r in records:
            if r.status and r.status.value == "OVERDUE":
                writer.writerow(
                    [r.equipment_id, r.type, r.site_id, r.expected_return_date, r.status.value]
                )
    elif report_type == "anomalies":
        writer.writerow(["Equipment ID", "Source", "Severity", "Reason", "Score", "Detected At"])
        for a in engine.anomalies:
            writer.writerow(
                [a.equipment_id, a.source.value, a.severity.value, a.reason, a.anomaly_score, a.detected_at]
            )
    elif report_type == "forecast":
        forecast = engine.forecast
        writer.writerow(
            ["Equipment Type", "Site", "Period Start", "Period End", "Predicted Demand", "Demand Level", "Model"]
        )
        if forecast:
            for item in forecast.items:
                writer.writerow(
                    [
                        item.equipment_type,
                        item.site_id,
                        item.period_start,
                        item.period_end,
                        item.predicted_demand,
                        item.demand_level,
                        item.model_name,
                    ]
                )
    else:
        raise HTTPException(status_code=400, detail="Unknown report_type")

    buffer.seek(0)
    return StreamingResponse(
        iter([buffer.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={report_type}_report.csv"},
    )


# ---------------------------------------------------------------------------
# Hybrid-cloud architecture APIs
# ---------------------------------------------------------------------------

@router.get("/hybrid/dashboard")
def hybrid_dashboard():
    """Ops console payload mapped to Edge + AWS hybrid architecture."""
    records = engine.get_enriched_records()
    forecast = engine.forecast
    items = forecast.items if forecast else []
    return build_hybrid_dashboard(records, items)


@router.get("/hybrid/architecture")
def hybrid_architecture():
    return system_topology()


@router.get("/hybrid/contracts")
def hybrid_contracts():
    return [to_contract(r) for r in engine.get_enriched_records()]


@router.get("/hybrid/live-state")
def hybrid_live_state():
    from services.hybrid import detect_architecture_anomalies

    records = engine.get_enriched_records()
    anoms = detect_architecture_anomalies(records)
    by_eq: dict[str, list[str]] = {}
    for a in anoms:
        by_eq.setdefault(a["equipment_id"], []).append(a["rule"])
    return [to_live_state(r, by_eq.get(r.equipment_id, [])) for r in records]


@router.get("/hybrid/telemetry")
def hybrid_telemetry():
    return [to_telemetry(r) for r in engine.get_enriched_records()]
