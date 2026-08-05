"""CSV parsing, validation, and preprocessing.

Never crashes on a single bad row — collects DataQualityIssues instead.
"""

from __future__ import annotations

import io
import logging
from datetime import date, datetime
from typing import Any, Optional

import pandas as pd

from models.schemas import DataQualityIssue, DataIngestionResult, EquipmentRecord

logger = logging.getLogger(__name__)

COLUMN_MAP = {
    "equipment id": "equipment_id",
    "equipment_id": "equipment_id",
    "type": "type",
    "site id": "site_id",
    "site_id": "site_id",
    "check-in date": "check_in_date",
    "check_in_date": "check_in_date",
    "check-in": "check_in_date",
    "check-out date": "check_out_date",
    "check_out_date": "check_out_date",
    "check-out": "check_out_date",
    "engine hours/day": "engine_hours_per_day",
    "engine_hours_per_day": "engine_hours_per_day",
    "engine hours": "engine_hours_per_day",
    "idle hours/day": "idle_hours_per_day",
    "idle_hours_per_day": "idle_hours_per_day",
    "idle hours": "idle_hours_per_day",
    "rental days": "rental_days",
    "rental_days": "rental_days",
    "last operator id": "last_operator_id",
    "last_operator_id": "last_operator_id",
    "operator id": "last_operator_id",
    "expected return date": "expected_return_date",
    "expected_return_date": "expected_return_date",
}

NULL_TOKENS = {"", "null", "none", "nan", "n/a", "na", "-"}


def _is_null(value: Any) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and pd.isna(value):
        return True
    if isinstance(value, str) and value.strip().lower() in NULL_TOKENS:
        return True
    try:
        if pd.isna(value):
            return True
    except (TypeError, ValueError):
        pass
    return False


def _parse_date(value: Any, field: str, row_idx: int, eq_id: Optional[str], issues: list) -> Optional[date]:
    if _is_null(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, pd.Timestamp):
        return value.date()
    try:
        parsed = pd.to_datetime(str(value).strip(), errors="coerce")
        if pd.isna(parsed):
            issues.append(
                DataQualityIssue(
                    row_index=row_idx,
                    equipment_id=eq_id,
                    field=field,
                    severity="ERROR",
                    message=f"Invalid date value '{value}' for {field}",
                )
            )
            return None
        return parsed.date()
    except Exception:
        issues.append(
            DataQualityIssue(
                row_index=row_idx,
                equipment_id=eq_id,
                field=field,
                severity="ERROR",
                message=f"Could not parse date '{value}' for {field}",
            )
        )
        return None


def _parse_float(value: Any, field: str, row_idx: int, eq_id: Optional[str], issues: list) -> Optional[float]:
    if _is_null(value):
        return None
    try:
        result = float(value)
        if result < 0:
            issues.append(
                DataQualityIssue(
                    row_index=row_idx,
                    equipment_id=eq_id,
                    field=field,
                    severity="ERROR",
                    message=f"Negative value {result} for {field}",
                )
            )
            return None
        return result
    except (TypeError, ValueError):
        issues.append(
            DataQualityIssue(
                row_index=row_idx,
                equipment_id=eq_id,
                field=field,
                severity="ERROR",
                message=f"Invalid numeric value '{value}' for {field}",
            )
        )
        return None


def _parse_int(value: Any, field: str, row_idx: int, eq_id: Optional[str], issues: list) -> Optional[int]:
    f = _parse_float(value, field, row_idx, eq_id, issues)
    if f is None:
        return None
    return int(f)


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    rename = {}
    for col in df.columns:
        key = str(col).strip().lower()
        if key in COLUMN_MAP:
            rename[col] = COLUMN_MAP[key]
    return df.rename(columns=rename)


def parse_csv_content(content: str | bytes, source: str = "unknown") -> DataIngestionResult:
    """Parse CSV text/bytes into EquipmentRecords with validation."""
    issues: list[DataQualityIssue] = []
    loaded_at = datetime.utcnow()

    try:
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig")
        df = pd.read_csv(io.StringIO(content))
    except Exception as exc:
        issues.append(
            DataQualityIssue(
                severity="CRITICAL",
                message=f"Failed to parse CSV from {source}: {exc}",
            )
        )
        return DataIngestionResult(
            records=[],
            issues=issues,
            source=source,
            loaded_at=loaded_at,
            row_count=0,
            valid_count=0,
            skipped_count=0,
        )

    if df.empty:
        issues.append(DataQualityIssue(severity="WARNING", message="CSV is empty"))
        return DataIngestionResult(
            records=[],
            issues=issues,
            source=source,
            loaded_at=loaded_at,
            row_count=0,
            valid_count=0,
            skipped_count=0,
        )

    df = _normalize_columns(df)
    if "equipment_id" not in df.columns:
        issues.append(
            DataQualityIssue(
                severity="CRITICAL",
                message="CSV missing required column: Equipment ID",
            )
        )
        return DataIngestionResult(
            records=[],
            issues=issues,
            source=source,
            loaded_at=loaded_at,
            row_count=len(df),
            valid_count=0,
            skipped_count=len(df),
        )

    records: list[EquipmentRecord] = []
    seen_ids: dict[str, int] = {}
    skipped = 0

    for idx, row in df.iterrows():
        row_idx = int(idx) + 2  # header + 1-based
        raw_id = row.get("equipment_id")
        if _is_null(raw_id):
            issues.append(
                DataQualityIssue(
                    row_index=row_idx,
                    severity="ERROR",
                    message="Missing Equipment ID — row skipped",
                )
            )
            skipped += 1
            continue

        eq_id = str(raw_id).strip()
        if eq_id in seen_ids:
            issues.append(
                DataQualityIssue(
                    row_index=row_idx,
                    equipment_id=eq_id,
                    severity="WARNING",
                    message=f"Duplicate Equipment ID (first seen at row {seen_ids[eq_id]}) — keeping first occurrence",
                )
            )
            skipped += 1
            continue
        seen_ids[eq_id] = row_idx

        eq_type = row.get("type")
        if _is_null(eq_type):
            issues.append(
                DataQualityIssue(
                    row_index=row_idx,
                    equipment_id=eq_id,
                    field="type",
                    severity="WARNING",
                    message="Missing equipment type — defaulting to Unknown",
                )
            )
            eq_type = "Unknown"
        else:
            eq_type = str(eq_type).strip()

        site_raw = row.get("site_id")
        site_id = None if _is_null(site_raw) else str(site_raw).strip()

        op_raw = row.get("last_operator_id")
        operator_id = None if _is_null(op_raw) else str(op_raw).strip()

        check_in = _parse_date(row.get("check_in_date"), "check_in_date", row_idx, eq_id, issues)
        check_out = _parse_date(row.get("check_out_date"), "check_out_date", row_idx, eq_id, issues)
        expected = _parse_date(
            row.get("expected_return_date") if "expected_return_date" in df.columns else None,
            "expected_return_date",
            row_idx,
            eq_id,
            issues,
        )

        if check_in and check_out and check_out < check_in:
            issues.append(
                DataQualityIssue(
                    row_index=row_idx,
                    equipment_id=eq_id,
                    field="check_out_date",
                    severity="ERROR",
                    message=(
                        f"Check-Out ({check_out}) is before Check-In ({check_in}). "
                        "Check-In = rented out; Check-Out = returned."
                    ),
                )
            )
            # Keep dates but flag — do not silently swap

        engine = _parse_float(row.get("engine_hours_per_day"), "engine_hours_per_day", row_idx, eq_id, issues)
        idle = _parse_float(row.get("idle_hours_per_day"), "idle_hours_per_day", row_idx, eq_id, issues)
        rental_days = _parse_int(row.get("rental_days"), "rental_days", row_idx, eq_id, issues)

        if site_id is None:
            issues.append(
                DataQualityIssue(
                    row_index=row_idx,
                    equipment_id=eq_id,
                    field="site_id",
                    severity="WARNING",
                    message="Missing Site ID",
                )
            )
        if operator_id is None:
            issues.append(
                DataQualityIssue(
                    row_index=row_idx,
                    equipment_id=eq_id,
                    field="last_operator_id",
                    severity="WARNING",
                    message="Missing Operator ID",
                )
            )

        records.append(
            EquipmentRecord(
                equipment_id=eq_id,
                type=eq_type,
                site_id=site_id,
                check_in_date=check_in,
                check_out_date=check_out,
                engine_hours_per_day=engine,
                idle_hours_per_day=idle,
                rental_days=rental_days,
                last_operator_id=operator_id,
                expected_return_date=expected,
            )
        )

    return DataIngestionResult(
        records=records,
        issues=issues,
        source=source,
        loaded_at=loaded_at,
        row_count=len(df),
        valid_count=len(records),
        skipped_count=skipped,
    )
