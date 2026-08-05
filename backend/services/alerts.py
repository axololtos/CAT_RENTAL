"""Overdue / return-approaching alert engine.

Uses Expected Return Date for active rentals — NEVER historical Check-Out Date.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from models.schemas import (
    Alert,
    AlertCategory,
    AlertSeverity,
    Anomaly,
    EquipmentRecord,
)
from services.database import new_id
from utils.config import Settings, get_settings
from utils.status import days_until_return, is_active_rental


def generate_return_alerts(
    records: list[EquipmentRecord],
    settings: Optional[Settings] = None,
    today: Optional[date] = None,
) -> list[Alert]:
    s = settings or get_settings()
    today = today or date.today()
    now = datetime.utcnow()
    alerts: list[Alert] = []

    for rec in records:
        if not is_active_rental(rec):
            continue
        if rec.expected_return_date is None:
            alerts.append(
                Alert(
                    id=new_id("alert"),
                    equipment_id=rec.equipment_id,
                    category=AlertCategory.RETURN_APPROACHING,
                    severity=AlertSeverity.WARNING,
                    title="Missing expected return date",
                    message=(
                        f"{rec.equipment_id} is currently rented out (checked in) "
                        "but has no Expected Return Date configured."
                    ),
                    detected_at=now,
                    metadata={"check_in_date": str(rec.check_in_date)},
                )
            )
            continue

        days_left = days_until_return(rec.expected_return_date, today)
        if days_left is None:
            continue

        if days_left < 0:
            alerts.append(
                Alert(
                    id=f"overdue_{rec.equipment_id}",
                    equipment_id=rec.equipment_id,
                    category=AlertCategory.OVERDUE,
                    severity=AlertSeverity.OVERDUE,
                    title="Overdue return",
                    message=(
                        f"{rec.equipment_id} ({rec.type}) is OVERDUE. "
                        f"Expected return was {rec.expected_return_date} "
                        f"({abs(days_left)} day(s) past due)."
                    ),
                    detected_at=now,
                    metadata={
                        "expected_return_date": str(rec.expected_return_date),
                        "days_overdue": abs(days_left),
                        "site_id": rec.site_id,
                    },
                )
            )
        elif days_left == 0:
            alerts.append(
                Alert(
                    id=f"due_today_{rec.equipment_id}",
                    equipment_id=rec.equipment_id,
                    category=AlertCategory.RETURN_APPROACHING,
                    severity=AlertSeverity.URGENT,
                    title="Due today",
                    message=(
                        f"{rec.equipment_id} ({rec.type}) is due for return TODAY "
                        f"({rec.expected_return_date})."
                    ),
                    detected_at=now,
                    metadata={"expected_return_date": str(rec.expected_return_date)},
                )
            )
        elif days_left <= s.due_tomorrow_days:
            alerts.append(
                Alert(
                    id=f"due_tomorrow_{rec.equipment_id}",
                    equipment_id=rec.equipment_id,
                    category=AlertCategory.RETURN_APPROACHING,
                    severity=AlertSeverity.WARNING,
                    title="Due tomorrow",
                    message=(
                        f"{rec.equipment_id} ({rec.type}) is due for return tomorrow "
                        f"({rec.expected_return_date})."
                    ),
                    detected_at=now,
                    metadata={"expected_return_date": str(rec.expected_return_date)},
                )
            )
        elif days_left <= s.due_soon_days:
            alerts.append(
                Alert(
                    id=f"due_soon_{rec.equipment_id}",
                    equipment_id=rec.equipment_id,
                    category=AlertCategory.RETURN_APPROACHING,
                    severity=AlertSeverity.REMINDER,
                    title="Return approaching",
                    message=(
                        f"{rec.equipment_id} ({rec.type}) is due in {days_left} day(s) "
                        f"({rec.expected_return_date})."
                    ),
                    detected_at=now,
                    metadata={
                        "expected_return_date": str(rec.expected_return_date),
                        "days_left": days_left,
                    },
                )
            )

    return alerts


def anomalies_to_alerts(anomalies: list[Anomaly]) -> list[Alert]:
    alerts: list[Alert] = []
    for a in anomalies:
        if a.source.value == "ML":
            category = AlertCategory.ANOMALY
            title = "Potential anomaly (ML)"
        else:
            category = AlertCategory.ANOMALY
            title = "Anomaly detected"
            if "utilization" in a.reason.lower() or "idle" in a.reason.lower():
                if a.severity in (AlertSeverity.WARNING, AlertSeverity.INFO):
                    category = AlertCategory.LOW_UTILIZATION

        alerts.append(
            Alert(
                id=f"anom_alert_{a.id}",
                equipment_id=a.equipment_id,
                category=category,
                severity=a.severity,
                title=title,
                message=a.reason,
                detected_at=a.detected_at,
                metadata={"source": a.source.value, **a.relevant_values},
            )
        )
    return alerts
