"""Rule-based anomaly detection."""

from __future__ import annotations

from datetime import datetime
from typing import Optional

from models.schemas import AlertSeverity, Anomaly, AnomalySource, EquipmentRecord
from services.database import new_id
from utils.config import Settings, get_settings
from utils.status import calculate_utilization


def detect_rule_anomalies(
    records: list[EquipmentRecord],
    settings: Optional[Settings] = None,
) -> list[Anomaly]:
    s = settings or get_settings()
    now = datetime.utcnow()
    anomalies: list[Anomaly] = []

    for rec in records:
        engine = rec.engine_hours_per_day
        idle = rec.idle_hours_per_day
        util = calculate_utilization(engine, idle)

        # High idle hours
        if idle is not None and idle >= s.idle_hours_anomaly_threshold:
            severity = AlertSeverity.CRITICAL if idle >= 10 else AlertSeverity.WARNING
            anomalies.append(
                Anomaly(
                    id=new_id("rule"),
                    equipment_id=rec.equipment_id,
                    source=AnomalySource.RULE,
                    severity=severity,
                    reason=f"High idle hours: {idle} idle hours/day recorded.",
                    detected_at=now,
                    relevant_values={"idle_hours_per_day": idle, "threshold": s.idle_hours_anomaly_threshold},
                )
            )

        # Zero engine + high idle
        if engine is not None and idle is not None and engine == 0 and idle >= s.idle_hours_anomaly_threshold:
            anomalies.append(
                Anomaly(
                    id=new_id("rule"),
                    equipment_id=rec.equipment_id,
                    source=AnomalySource.RULE,
                    severity=AlertSeverity.CRITICAL,
                    reason=f"{idle} idle hours recorded with zero engine hours — possible unused rental.",
                    detected_at=now,
                    relevant_values={"engine_hours_per_day": engine, "idle_hours_per_day": idle},
                )
            )

        # Missing site
        if rec.site_id is None:
            anomalies.append(
                Anomaly(
                    id=new_id("rule"),
                    equipment_id=rec.equipment_id,
                    source=AnomalySource.RULE,
                    severity=AlertSeverity.WARNING,
                    reason="Missing Site ID — equipment location unaccounted for.",
                    detected_at=now,
                    relevant_values={"site_id": None},
                )
            )

        # Missing operator
        if rec.last_operator_id is None:
            anomalies.append(
                Anomaly(
                    id=new_id("rule"),
                    equipment_id=rec.equipment_id,
                    source=AnomalySource.RULE,
                    severity=AlertSeverity.WARNING,
                    reason="Missing Operator ID — no assigned operator.",
                    detected_at=now,
                    relevant_values={"last_operator_id": None},
                )
            )

        # Activity without operator
        if engine is not None and engine > 0 and rec.last_operator_id is None:
            anomalies.append(
                Anomaly(
                    id=new_id("rule"),
                    equipment_id=rec.equipment_id,
                    source=AnomalySource.RULE,
                    severity=AlertSeverity.CRITICAL,
                    reason=f"Machine activity ({engine} engine hrs/day) without assigned operator.",
                    detected_at=now,
                    relevant_values={"engine_hours_per_day": engine, "last_operator_id": None},
                )
            )

        # Activity without site
        if engine is not None and engine > 0 and rec.site_id is None:
            anomalies.append(
                Anomaly(
                    id=new_id("rule"),
                    equipment_id=rec.equipment_id,
                    source=AnomalySource.RULE,
                    severity=AlertSeverity.CRITICAL,
                    reason=f"Machine activity ({engine} engine hrs/day) without assigned site.",
                    detected_at=now,
                    relevant_values={"engine_hours_per_day": engine, "site_id": None},
                )
            )

        # Combined: high idle + no site/operator (classic sample case EQX1002/1007)
        if (
            idle is not None
            and idle >= s.idle_hours_anomaly_threshold
            and rec.site_id is None
            and rec.last_operator_id is None
        ):
            anomalies.append(
                Anomaly(
                    id=new_id("rule"),
                    equipment_id=rec.equipment_id,
                    source=AnomalySource.RULE,
                    severity=AlertSeverity.CRITICAL,
                    reason=f"{idle} idle hours recorded with no assigned site/operator.",
                    detected_at=now,
                    relevant_values={
                        "idle_hours_per_day": idle,
                        "site_id": None,
                        "last_operator_id": None,
                    },
                )
            )

        # Unusually long rental
        rental_days = rec.rental_days
        if rental_days is None and rec.check_in_date and rec.check_out_date:
            rental_days = (rec.check_out_date - rec.check_in_date).days
        elif rental_days is None and rec.check_in_date and rec.check_out_date is None:
            from datetime import date

            rental_days = (date.today() - rec.check_in_date).days

        if rental_days is not None and rental_days >= s.long_rental_days_threshold:
            anomalies.append(
                Anomaly(
                    id=new_id("rule"),
                    equipment_id=rec.equipment_id,
                    source=AnomalySource.RULE,
                    severity=AlertSeverity.WARNING,
                    reason=f"Unusually long rental duration: {rental_days} days.",
                    detected_at=now,
                    relevant_values={"rental_days": rental_days, "threshold": s.long_rental_days_threshold},
                )
            )

        # Unexpectedly high engine hours
        if engine is not None and engine >= s.high_engine_hours_threshold:
            anomalies.append(
                Anomaly(
                    id=new_id("rule"),
                    equipment_id=rec.equipment_id,
                    source=AnomalySource.RULE,
                    severity=AlertSeverity.WARNING,
                    reason=f"Unexpectedly high engine hours: {engine} hrs/day.",
                    detected_at=now,
                    relevant_values={"engine_hours_per_day": engine, "threshold": s.high_engine_hours_threshold},
                )
            )

        # Very low utilization
        if util is not None and util <= s.low_utilization_anomaly_threshold:
            anomalies.append(
                Anomaly(
                    id=new_id("rule"),
                    equipment_id=rec.equipment_id,
                    source=AnomalySource.RULE,
                    severity=AlertSeverity.WARNING,
                    reason=f"Very low utilization: {util}%.",
                    detected_at=now,
                    relevant_values={"utilization_pct": util, "threshold": s.low_utilization_anomaly_threshold},
                )
            )

    return anomalies
