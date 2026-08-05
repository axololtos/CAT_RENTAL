"""Hybrid-cloud domain projection.

Maps CSV rental rows into the proposed architecture:
  - RentalContracts (DynamoDB-style)
  - EquipmentLiveState (DynamoDB-style)
  - Edge telemetry payloads (MQTT fleet/telemetry/v1)
  - Architecture anomaly rules (UNASSIGNED_USAGE, UNDER_UTILIZED, MISSING_OPERATOR)

CSV column semantics (problem statement) are preserved internally:
  Check-In Date  = rental start / leaves yard
  Check-Out Date = rental end / returns to yard

Architecture UI labels:
  Dispatch (Check-Out) = start rental
  Return (Check-In)    = end rental
"""

from __future__ import annotations

import hashlib
from datetime import date, datetime, timedelta, timezone
from typing import Any, Optional

from models.schemas import EquipmentRecord
from utils.status import calculate_utilization, is_active_rental


def _stable_float(key: str, lo: float, hi: float) -> float:
    digest = hashlib.sha256(key.encode()).hexdigest()
    n = int(digest[:8], 16) / 0xFFFFFFFF
    return round(lo + n * (hi - lo), 2)


def _site_coords(site_id: Optional[str]) -> tuple[float, float]:
    coords = {
        "S001": (12.9716, 77.5946),
        "S002": (13.0827, 80.2707),
        "S003": (17.3850, 78.4867),
        "S004": (19.0760, 72.8777),
        "S006": (28.6139, 77.2090),
    }
    if site_id and site_id in coords:
        return coords[site_id]
    # Unassigned / unknown — offset from depot
    return (12.90 + _stable_float(f"lat-{site_id}", 0, 0.2), 77.50 + _stable_float(f"lon-{site_id}", 0, 0.2))


def contract_status(record: EquipmentRecord) -> str:
    if is_active_rental(record):
        if record.expected_return_date and record.expected_return_date < date.today():
            return "CRITICAL_OVERDUE"
        return "ACTIVE"
    if record.check_out_date:
        return "RETURNED"
    return "AVAILABLE"


def to_contract(record: EquipmentRecord) -> dict[str, Any]:
    """DynamoDB RentalContracts projection."""
    return {
        "equipment_id": record.equipment_id,
        "equipment_type": record.type,
        "site_id": record.site_id,
        # Architecture: dispatch start / return end (CSV Check-In / Check-Out)
        "dispatch_date": record.check_in_date.isoformat() if record.check_in_date else None,
        "return_date": record.check_out_date.isoformat() if record.check_out_date else None,
        "check_in_date": record.check_in_date.isoformat() if record.check_in_date else None,
        "check_out_date": record.check_out_date.isoformat() if record.check_out_date else None,
        "expected_return_date": (
            record.expected_return_date.isoformat() if record.expected_return_date else None
        ),
        "rental_days": record.rental_days,
        "status": contract_status(record),
        "last_operator_id": record.last_operator_id,
    }


def to_live_state(record: EquipmentRecord, anomaly_codes: list[str]) -> dict[str, Any]:
    """DynamoDB EquipmentLiveState projection with simulated telematics."""
    lat, lon = _site_coords(record.site_id)
    engine = record.engine_hours_per_day or 0.0
    idle = record.idle_hours_per_day or 0.0
    # Cumulative-style totals for architecture telemetry demo
    engine_total = round(3000 + engine * (record.rental_days or 10) * 1.2, 1)
    idle_total = round(800 + idle * (record.rental_days or 10) * 1.1, 1)
    fuel = _stable_float(f"fuel-{record.equipment_id}", 12, 95)
    primary_anomaly = anomaly_codes[0] if anomaly_codes else "NORMAL"

    return {
        "equipment_id": record.equipment_id,
        "equipment_type": record.type,
        "last_operator_id": record.last_operator_id,
        "site_id": record.site_id,
        "lat": lat,
        "lon": lon,
        "fuel_pct": fuel,
        "engine_hours": engine,
        "idle_hours": idle,
        "engine_hours_total": engine_total,
        "idle_hours_total": idle_total,
        "utilization_pct": calculate_utilization(record.engine_hours_per_day, record.idle_hours_per_day),
        "anomaly_status": primary_anomaly,
        "anomaly_codes": anomaly_codes,
        "contract_status": contract_status(record),
        "gateway_id": f"GW-{(record.site_id or 'UNASSIGNED')}-01",
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "edge_online": True,
    }


def to_telemetry(record: EquipmentRecord) -> dict[str, Any]:
    """MQTT topic fleet/telemetry/v1 payload."""
    state = to_live_state(record, [])
    return {
        "equipment_id": record.equipment_id,
        "gateway_id": state["gateway_id"],
        "operator_id": record.last_operator_id,
        "telemetry": {
            "engine_hours_total": state["engine_hours_total"],
            "idle_hours_total": state["idle_hours_total"],
            "engine_hours_per_day": record.engine_hours_per_day,
            "idle_hours_per_day": record.idle_hours_per_day,
            "fuel_level_pct": state["fuel_pct"],
            "location": {"latitude": state["lat"], "longitude": state["lon"]},
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "topic": "fleet/telemetry/v1",
    }


def detect_architecture_anomalies(records: list[EquipmentRecord]) -> list[dict[str, Any]]:
    """Real-time rules from the hybrid-cloud architecture proposal."""
    now = datetime.now(timezone.utc)
    findings: list[dict[str, Any]] = []

    for rec in records:
        engine = rec.engine_hours_per_day
        idle = rec.idle_hours_per_day
        eng = engine if engine is not None else 0.0
        idl = idle if idle is not None else 0.0

        # Rule 1: Unassigned Asset Usage (site NULL + activity)
        if rec.site_id is None and (eng > 0 or idl > 0):
            findings.append(
                {
                    "id": f"arch_unassigned_{rec.equipment_id}",
                    "equipment_id": rec.equipment_id,
                    "rule": "UNASSIGNED_USAGE",
                    "severity": "CRITICAL",
                    "title": "Unassigned asset usage",
                    "reason": (
                        f"{rec.equipment_id} shows activity "
                        f"(engine={eng}, idle={idl}) but RentalContracts.site_id is NULL — geofence/contract breach."
                    ),
                    "action": "Mark anomaly_status=UNASSIGNED_USAGE · SNS critical alert · dashboard highlight",
                    "layer": "AWS IoT Rule → Anomaly Lambda → SNS",
                    "detected_at": now.isoformat(),
                    "relevant_values": {
                        "site_id": None,
                        "engine_hours_per_day": eng,
                        "idle_hours_per_day": idl,
                    },
                }
            )

        # Rule 2: Excessive Idling — idle/engine > 0.60 (24h window proxy = daily rates)
        if eng > 0 and (idl / eng) > 0.60:
            ratio = round(idl / eng, 2)
            findings.append(
                {
                    "id": f"arch_idle_{rec.equipment_id}",
                    "equipment_id": rec.equipment_id,
                    "rule": "UNDER_UTILIZED",
                    "severity": "WARNING",
                    "title": "Excessive idling",
                    "reason": (
                        f"Idle/engine ratio {ratio} exceeds 0.60 threshold "
                        f"(idle={idl}, engine={eng})."
                    ),
                    "action": "Flag UNDER_UTILIZED · prompt re-allocation recommendation",
                    "layer": "AWS IoT Rule → Anomaly Lambda",
                    "detected_at": now.isoformat(),
                    "relevant_values": {
                        "idle_hours_per_day": idl,
                        "engine_hours_per_day": eng,
                        "idle_engine_ratio": ratio,
                        "threshold": 0.60,
                    },
                }
            )
        elif eng == 0 and idl >= 8:
            findings.append(
                {
                    "id": f"arch_idle_zero_{rec.equipment_id}",
                    "equipment_id": rec.equipment_id,
                    "rule": "UNDER_UTILIZED",
                    "severity": "WARNING",
                    "title": "Excessive idling (zero engine)",
                    "reason": f"Zero engine hours with {idl} idle hours — unused rental signal.",
                    "action": "Flag UNDER_UTILIZED · prompt re-allocation recommendation",
                    "layer": "AWS IoT Rule → Anomaly Lambda",
                    "detected_at": now.isoformat(),
                    "relevant_values": {"idle_hours_per_day": idl, "engine_hours_per_day": 0},
                }
            )

        # Rule 3: Missing Operator Authentication
        if eng > 0 and rec.last_operator_id is None:
            findings.append(
                {
                    "id": f"arch_operator_{rec.equipment_id}",
                    "equipment_id": rec.equipment_id,
                    "rule": "MISSING_OPERATOR",
                    "severity": "CRITICAL",
                    "title": "Missing operator authentication",
                    "reason": (
                        f"Engine activity ({eng} hrs/day) while operator_id is NULL — "
                        "unauthorized usage."
                    ),
                    "action": "Greengrass local alarm + unauthorized usage log",
                    "layer": "Edge Lambda (Greengrass) + Cloud Anomaly Lambda",
                    "detected_at": now.isoformat(),
                    "relevant_values": {
                        "operator_id": None,
                        "engine_hours_per_day": eng,
                    },
                }
            )

    return findings


def overdue_from_contracts(contracts: list[dict[str, Any]], today: Optional[date] = None) -> list[dict[str, Any]]:
    """EventBridge-style overdue engine using expected/return due date."""
    today = today or date.today()
    alerts = []
    for c in contracts:
        if c["status"] not in ("ACTIVE", "CRITICAL_OVERDUE"):
            continue
        due_raw = c.get("expected_return_date") or c.get("check_out_date")
        if not due_raw:
            continue
        due = date.fromisoformat(due_raw)
        remaining = (due - today).days
        if remaining < 0:
            alerts.append(
                {
                    "equipment_id": c["equipment_id"],
                    "severity": "CRITICAL_OVERDUE",
                    "remaining_days": remaining,
                    "due_date": due_raw,
                    "message": f"{c['equipment_id']} past due ({abs(remaining)}d). Dispatch SNS critical overdue.",
                }
            )
        elif remaining <= 2:
            alerts.append(
                {
                    "equipment_id": c["equipment_id"],
                    "severity": "RETURN_REMINDER",
                    "remaining_days": remaining,
                    "due_date": due_raw,
                    "message": f"{c['equipment_id']} return reminder — {remaining}d remaining.",
                }
            )
    return alerts


def system_topology() -> dict[str, Any]:
    """Hybrid-cloud component health for the ops console."""
    now = datetime.now(timezone.utc).isoformat()
    return {
        "architecture": "Hybrid-Cloud (Edge + AWS)",
        "updated_at": now,
        "edge": [
            {"id": "mobile_scanner", "name": "Mobile App / QR-RFID Scanner", "status": "ONLINE", "layer": "ON-SITE"},
            {"id": "can_bus", "name": "CAN Bus ECU Telemetry", "status": "ONLINE", "layer": "ON-SITE"},
            {"id": "rfid_reader", "name": "Operator RFID Reader", "status": "ONLINE", "layer": "ON-SITE"},
            {
                "id": "greengrass",
                "name": "AWS IoT Greengrass Core",
                "status": "ONLINE",
                "layer": "ON-SITE",
                "detail": "Stream Manager SQLite buffer · Edge Lambda safety checks",
            },
        ],
        "cloud": [
            {"id": "iot_core", "name": "AWS IoT Core", "status": "ONLINE", "layer": "AWS"},
            {"id": "api_gateway", "name": "API Gateway", "status": "ONLINE", "layer": "AWS"},
            {"id": "contract_lambda", "name": "Contract Lambda", "status": "ONLINE", "layer": "AWS"},
            {"id": "anomaly_lambda", "name": "Anomaly Lambda", "status": "ONLINE", "layer": "AWS"},
            {"id": "dynamodb", "name": "DynamoDB (Contracts & Live State)", "status": "ONLINE", "layer": "AWS"},
            {"id": "firehose", "name": "Amazon Data Firehose", "status": "ONLINE", "layer": "AWS"},
            {"id": "s3", "name": "S3 Data Lake (Parquet)", "status": "ONLINE", "layer": "AWS"},
            {"id": "sagemaker", "name": "SageMaker / Athena Forecast", "status": "ONLINE", "layer": "AWS"},
            {"id": "sns", "name": "SNS / CloudWatch Alerts", "status": "ONLINE", "layer": "AWS"},
            {"id": "eventbridge", "name": "EventBridge Overdue Scheduler", "status": "ONLINE", "layer": "AWS"},
        ],
        "data_flows": [
            {
                "from": "Greengrass",
                "to": "IoT Core",
                "protocol": "MQTT/TLS",
                "note": "Auto-sync on reconnect · offline SQLite buffer",
            },
            {"from": "IoT Core", "to": "Firehose → S3", "protocol": "IoT Rule", "note": "Partitioned Parquet lake"},
            {"from": "IoT Core", "to": "Anomaly Lambda", "protocol": "IoT Rule", "note": "Real-time misuse rules"},
            {"from": "Mobile Scanner", "to": "API Gateway → Contract Lambda", "protocol": "HTTPS", "note": "Dispatch / Return"},
            {"from": "S3 Lake", "to": "SageMaker", "protocol": "Batch", "note": "14-day demand forecast"},
            {"from": "Anomaly Lambda", "to": "SNS + Dashboard", "protocol": "Event", "note": "SMS/Email + UI highlight"},
        ],
        "prototype_note": (
            "This console prototypes the hybrid-cloud architecture against local/CSV sample data. "
            "Edge and AWS component statuses are simulated as ONLINE for demonstration."
        ),
    }


def build_hybrid_dashboard(
    records: list[EquipmentRecord],
    forecast_items: Optional[list] = None,
) -> dict[str, Any]:
    arch_anoms = detect_architecture_anomalies(records)
    by_eq: dict[str, list[str]] = {}
    for a in arch_anoms:
        by_eq.setdefault(a["equipment_id"], []).append(a["rule"])

    contracts = [to_contract(r) for r in records]
    live_states = [to_live_state(r, by_eq.get(r.equipment_id, [])) for r in records]
    telemetry = [to_telemetry(r) for r in records]
    overdue = overdue_from_contracts(contracts)

    active = sum(1 for c in contracts if c["status"] in ("ACTIVE", "CRITICAL_OVERDUE"))
    returned = sum(1 for c in contracts if c["status"] == "RETURNED")
    critical = sum(1 for a in arch_anoms if a["severity"] == "CRITICAL")
    under = sum(1 for a in arch_anoms if a["rule"] == "UNDER_UTILIZED")
    unassigned = sum(1 for a in arch_anoms if a["rule"] == "UNASSIGNED_USAGE")

    high_demand = []
    if forecast_items:
        high_demand = [
            {
                "equipment_type": getattr(i, "equipment_type", i.get("equipment_type")),
                "site_id": getattr(i, "site_id", i.get("site_id")),
                "predicted_demand": getattr(i, "predicted_demand", i.get("predicted_demand")),
                "demand_level": getattr(i, "demand_level", i.get("demand_level")),
            }
            for i in forecast_items
            if getattr(i, "demand_level", None) == "HIGH" or (isinstance(i, dict) and i.get("demand_level") == "HIGH")
        ][:6]

    return {
        "kpis": {
            "fleet_size": len(records),
            "active_contracts": active,
            "returned_contracts": returned,
            "live_assets_online": len(live_states),
            "critical_anomalies": critical,
            "under_utilized": under,
            "unassigned_usage": unassigned,
            "overdue_alerts": len([o for o in overdue if o["severity"] == "CRITICAL_OVERDUE"]),
            "return_reminders": len([o for o in overdue if o["severity"] == "RETURN_REMINDER"]),
            "avg_fuel_pct": round(sum(s["fuel_pct"] for s in live_states) / max(len(live_states), 1), 1),
            "avg_utilization_pct": round(
                sum(s["utilization_pct"] or 0 for s in live_states) / max(len(live_states), 1),
                1,
            ),
        },
        "contracts": contracts,
        "live_state": live_states,
        "telemetry": telemetry,
        "architecture_anomalies": arch_anoms,
        "overdue_engine": overdue,
        "demand_forecast_preview": high_demand,
        "topology": system_topology(),
        "workflow": {
            "dispatch": {
                "architecture_name": "Check-Out (Dispatch)",
                "description": "Manager scans QR/RFID → API Gateway → Contract Lambda creates ACTIVE contract",
            },
            "return": {
                "architecture_name": "Check-In (Return)",
                "description": "Manager scans on return → Lambda marks RETURNED and clears site assignment",
            },
            "csv_mapping": {
                "check_in_date": "Rental start (equipment leaves yard)",
                "check_out_date": "Rental end (equipment returns to yard)",
            },
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }
