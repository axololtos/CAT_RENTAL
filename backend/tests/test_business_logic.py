"""Critical business logic tests — Check-In/Out terminology, utilization, alerts, anomalies."""

from datetime import date, timedelta

import pytest

from models.schemas import EquipmentRecord
from services.ingestion import parse_csv_content
from services.rule_anomalies import detect_rule_anomalies
from services.alerts import generate_return_alerts
from utils.status import (
    calculate_status,
    calculate_utilization,
    is_active_rental,
    utilization_category,
)
from models.schemas import EquipmentStatus, UtilizationCategory
from utils.config import Settings


def test_check_in_means_leaves_company():
    """Check-In date present + no Check-Out = rented out (left company)."""
    rec = EquipmentRecord(
        equipment_id="EQX1",
        type="Excavator",
        check_in_date=date(2026, 7, 1),
        check_out_date=None,
        expected_return_date=date(2026, 8, 15),
    )
    assert is_active_rental(rec) is True
    assert calculate_status(rec, today=date(2026, 8, 1)) == EquipmentStatus.RENTED


def test_check_out_means_returned():
    """Check-Out date present = returned to company = AVAILABLE."""
    rec = EquipmentRecord(
        equipment_id="EQX1",
        type="Excavator",
        check_in_date=date(2025, 4, 1),
        check_out_date=date(2025, 4, 16),
        engine_hours_per_day=5,
        idle_hours_per_day=2,
    )
    assert is_active_rental(rec) is False
    assert calculate_status(rec) == EquipmentStatus.AVAILABLE


def test_utilization_formula():
    assert calculate_utilization(1.5, 10) == pytest.approx(13.04, abs=0.01)
    assert calculate_utilization(8, 0) == 100.0
    assert calculate_utilization(0, 0) == 0.0
    assert calculate_utilization(None, 5) is None
    assert calculate_utilization(5, None) is None


def test_zero_hour_utilization():
    assert calculate_utilization(0, 11) == 0.0
    assert utilization_category(0.0) == UtilizationCategory.LOW


def test_overdue_uses_expected_return_not_checkout():
    """Must use Expected Return Date, not historical Check-Out."""
    rec = EquipmentRecord(
        equipment_id="EQX9",
        type="Crane",
        site_id="S001",
        check_in_date=date(2026, 7, 15),
        check_out_date=None,
        expected_return_date=date(2026, 8, 1),
        engine_hours_per_day=4,
        idle_hours_per_day=5,
    )
    today = date(2026, 8, 5)
    assert calculate_status(rec, today=today) == EquipmentStatus.OVERDUE
    alerts = generate_return_alerts([rec], today=today)
    assert any(a.severity.value == "OVERDUE" for a in alerts)


def test_due_soon_calculation():
    rec = EquipmentRecord(
        equipment_id="EQX8",
        type="Excavator",
        site_id="S002",
        check_in_date=date(2026, 7, 20),
        check_out_date=None,
        expected_return_date=date(2026, 8, 7),
        engine_hours_per_day=6,
        idle_hours_per_day=2,
    )
    today = date(2026, 8, 5)
    assert calculate_status(rec, today=today) == EquipmentStatus.DUE_SOON


def test_missing_values_safe():
    csv = "Equipment ID,Type,Site ID,Check-In Date,Check-Out Date,Engine Hours/Day,Idle Hours/Day,Rental Days,Last Operator ID\n"
    csv += "EQX1002,Crane,,2025-03-10,2025-03-30,0,11,20,\n"
    result = parse_csv_content(csv, source="test")
    assert result.valid_count == 1
    assert result.records[0].site_id is None
    assert result.records[0].last_operator_id is None


def test_invalid_dates_flagged():
    csv = "Equipment ID,Type,Site ID,Check-In Date,Check-Out Date,Engine Hours/Day,Idle Hours/Day,Rental Days,Last Operator ID\n"
    csv += "EQX1,Excavator,S001,not-a-date,2025-04-16,1,2,5,OP1\n"
    result = parse_csv_content(csv, source="test")
    assert any("Invalid date" in i.message for i in result.issues)


def test_checkout_before_checkin_flagged():
    csv = "Equipment ID,Type,Site ID,Check-In Date,Check-Out Date,Engine Hours/Day,Idle Hours/Day,Rental Days,Last Operator ID\n"
    csv += "EQX1,Excavator,S001,2025-04-16,2025-04-01,1,2,5,OP1\n"
    result = parse_csv_content(csv, source="test")
    assert any("before Check-In" in i.message for i in result.issues)


def test_anomaly_rules_high_idle_no_site():
    rec = EquipmentRecord(
        equipment_id="EQX1002",
        type="Crane",
        site_id=None,
        check_in_date=date(2025, 3, 10),
        check_out_date=date(2025, 3, 30),
        engine_hours_per_day=0,
        idle_hours_per_day=11,
        rental_days=20,
        last_operator_id=None,
    )
    anoms = detect_rule_anomalies([rec])
    assert any("no assigned site/operator" in a.reason for a in anoms)
    assert any(a.severity.value == "CRITICAL" for a in anoms)


def test_negative_hours_rejected():
    csv = "Equipment ID,Type,Site ID,Check-In Date,Check-Out Date,Engine Hours/Day,Idle Hours/Day,Rental Days,Last Operator ID\n"
    csv += "EQX1,Excavator,S001,2025-04-01,2025-04-16,-1,2,5,OP1\n"
    result = parse_csv_content(csv, source="test")
    assert any("Negative" in i.message for i in result.issues)
    assert result.records[0].engine_hours_per_day is None


def test_duplicate_ids_skipped():
    csv = "Equipment ID,Type,Site ID,Check-In Date,Check-Out Date,Engine Hours/Day,Idle Hours/Day,Rental Days,Last Operator ID\n"
    csv += "EQX1,Excavator,S001,2025-04-01,2025-04-16,1,2,5,OP1\n"
    csv += "EQX1,Excavator,S002,2025-05-01,2025-05-16,1,2,5,OP2\n"
    result = parse_csv_content(csv, source="test")
    assert result.valid_count == 1
    assert result.skipped_count == 1
