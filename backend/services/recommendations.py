"""Rule-based smart recommendations from utilization, demand, status, anomalies."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from models.schemas import (
    Anomaly,
    EquipmentRecord,
    EquipmentStatus,
    ForecastItem,
    Recommendation,
)
from services.database import new_id
from utils.status import calculate_utilization, is_active_rental


def generate_recommendations(
    records: list[EquipmentRecord],
    anomalies: list[Anomaly],
    forecast_items: list[ForecastItem],
) -> list[Recommendation]:
    now = datetime.utcnow()
    recs: list[Recommendation] = []

    # Low utilization on active rentals
    for r in records:
        util = calculate_utilization(r.engine_hours_per_day, r.idle_hours_per_day)
        if util is not None and util < 30 and is_active_rental(r):
            recs.append(
                Recommendation(
                    id=new_id("rec"),
                    equipment_id=r.equipment_id,
                    site_id=r.site_id,
                    equipment_type=r.type,
                    priority="HIGH",
                    message=f"{r.equipment_id} has low utilization ({util}%) at {r.site_id or 'unassigned site'}.",
                    rationale="Active rental with utilization below 30%.",
                    created_at=now,
                )
            )

    # High idle + missing operator
    for r in records:
        idle = r.idle_hours_per_day or 0
        if idle >= 8 and r.last_operator_id is None:
            recs.append(
                Recommendation(
                    id=new_id("rec"),
                    equipment_id=r.equipment_id,
                    site_id=r.site_id,
                    equipment_type=r.type,
                    priority="CRITICAL",
                    message=(
                        f"{r.equipment_id} has high idle hours ({idle}) and no assigned operator. "
                        "Verify assignment."
                    ),
                    rationale="High idle with missing operator indicates possible misallocation.",
                    created_at=now,
                )
            )

    # Available equipment that could fill forecast demand
    available = [
        r
        for r in records
        if r.status in (EquipmentStatus.AVAILABLE, None) and not is_active_rental(r)
    ]
    high_demand = [f for f in forecast_items if f.demand_level == "HIGH"]

    for f in high_demand[:10]:
        recs.append(
            Recommendation(
                id=new_id("rec"),
                site_id=f.site_id,
                equipment_type=f.equipment_type,
                priority="MEDIUM",
                message=(
                    f"{f.equipment_type} demand at {f.site_id} is forecast to increase "
                    f"(predicted demand: {f.predicted_demand}, level: {f.demand_level})."
                ),
                rationale="Demand forecast indicates elevated need for pre-positioning.",
                created_at=now,
            )
        )
        match = next((a for a in available if a.type == f.equipment_type), None)
        if match:
            recs.append(
                Recommendation(
                    id=new_id("rec"),
                    equipment_id=match.equipment_id,
                    site_id=f.site_id,
                    equipment_type=f.equipment_type,
                    priority="HIGH",
                    message=(
                        f"Consider reallocating available {match.type} {match.equipment_id} "
                        f"to {f.site_id}."
                    ),
                    rationale="Available unit of matching type for high-demand site.",
                    created_at=now,
                )
            )
            available = [a for a in available if a.equipment_id != match.equipment_id]

    # Overdue equipment
    for r in records:
        if r.status == EquipmentStatus.OVERDUE:
            recs.append(
                Recommendation(
                    id=new_id("rec"),
                    equipment_id=r.equipment_id,
                    site_id=r.site_id,
                    equipment_type=r.type,
                    priority="CRITICAL",
                    message=(
                        f"{r.equipment_id} is overdue for return. "
                        "Contact site operator and schedule check-out."
                    ),
                    rationale="Expected return date has passed.",
                    created_at=now,
                )
            )

    # Critical anomalies without duplicate messages
    seen_eq = {r.equipment_id for r in recs if r.equipment_id}
    for a in anomalies:
        if a.severity.value == "CRITICAL" and a.equipment_id not in seen_eq:
            recs.append(
                Recommendation(
                    id=new_id("rec"),
                    equipment_id=a.equipment_id,
                    priority="HIGH",
                    message=f"Investigate {a.equipment_id}: {a.reason}",
                    rationale=f"Triggered by {a.source.value} anomaly detection.",
                    created_at=now,
                )
            )
            seen_eq.add(a.equipment_id)

    # Deduplicate by message
    unique: list[Recommendation] = []
    seen_msg = set()
    for r in recs:
        if r.message not in seen_msg:
            unique.append(r)
            seen_msg.add(r.message)

    priority_order = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}
    unique.sort(key=lambda x: priority_order.get(x.priority, 9))
    return unique[:50]
