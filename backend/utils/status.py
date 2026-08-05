"""Centralized status and utilization calculations.

CHECK-IN  = equipment leaves the company (rented out)
CHECK-OUT = equipment returns to the company
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from models.schemas import EquipmentRecord, EquipmentStatus, UtilizationCategory
from utils.config import Settings, get_settings


def calculate_utilization(
    engine_hours: Optional[float],
    idle_hours: Optional[float],
) -> Optional[float]:
    """Utilization % = Engine Hours / (Engine Hours + Idle Hours) * 100."""
    if engine_hours is None or idle_hours is None:
        return None
    if engine_hours < 0 or idle_hours < 0:
        return None
    total = engine_hours + idle_hours
    if total == 0:
        return 0.0
    return round((engine_hours / total) * 100, 2)


def utilization_category(
    utilization_pct: Optional[float],
    settings: Optional[Settings] = None,
) -> UtilizationCategory:
    if utilization_pct is None:
        return UtilizationCategory.UNKNOWN
    s = settings or get_settings()
    if utilization_pct < s.util_low_max:
        return UtilizationCategory.LOW
    if utilization_pct < s.util_moderate_max:
        return UtilizationCategory.MODERATE
    if utilization_pct < s.util_good_max:
        return UtilizationCategory.GOOD
    return UtilizationCategory.HIGH


def is_active_rental(record: EquipmentRecord) -> bool:
    """Active rental = has check-in (left company) and no check-out (not returned)."""
    return record.check_in_date is not None and record.check_out_date is None


def days_until_return(expected_return: Optional[date], today: Optional[date] = None) -> Optional[int]:
    if expected_return is None:
        return None
    today = today or date.today()
    return (expected_return - today).days


def calculate_status(
    record: EquipmentRecord,
    has_anomaly: bool = False,
    settings: Optional[Settings] = None,
    today: Optional[date] = None,
) -> EquipmentStatus:
    """Single source of truth for equipment status.

    Priority (highest first for display of primary status):
    OVERDUE > DUE SOON > ANOMALY > UNDER-UTILIZED > RENTED > AVAILABLE
    """
    s = settings or get_settings()
    today = today or date.today()

    if is_active_rental(record):
        days_left = days_until_return(record.expected_return_date, today)
        if days_left is not None and days_left < 0:
            return EquipmentStatus.OVERDUE
        if days_left is not None and days_left <= s.due_soon_days:
            return EquipmentStatus.DUE_SOON
        if has_anomaly:
            return EquipmentStatus.ANOMALY
        util = calculate_utilization(record.engine_hours_per_day, record.idle_hours_per_day)
        if util is not None and util < s.util_low_max:
            return EquipmentStatus.UNDER_UTILIZED
        return EquipmentStatus.RENTED

    # Completed / available equipment
    if has_anomaly:
        return EquipmentStatus.ANOMALY
    util = calculate_utilization(record.engine_hours_per_day, record.idle_hours_per_day)
    if util is not None and util < s.util_low_max and record.check_out_date is not None:
        # Historical under-utilization still flagged for visibility
        return EquipmentStatus.UNDER_UTILIZED
    return EquipmentStatus.AVAILABLE


def enrich_record(
    record: EquipmentRecord,
    has_anomaly: bool = False,
    settings: Optional[Settings] = None,
    today: Optional[date] = None,
) -> EquipmentRecord:
    """Attach derived fields to an equipment record."""
    s = settings or get_settings()
    util = calculate_utilization(record.engine_hours_per_day, record.idle_hours_per_day)
    record.utilization_pct = util
    record.utilization_category = utilization_category(util, s)
    record.is_active_rental = is_active_rental(record)
    record.status = calculate_status(record, has_anomaly=has_anomaly, settings=s, today=today)
    return record
