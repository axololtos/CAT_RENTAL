"""Append user-submitted equipment rows into the live fleet dataset."""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Optional

from fastapi import HTTPException

from models.schemas import AppendEquipmentRequest, EquipmentRecord
from services import database as db
from services.data_store import store, BACKEND_ROOT
from utils.config import get_settings


def _nullish(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    cleaned = value.strip()
    if cleaned == "" or cleaned.upper() == "NULL":
        return None
    return cleaned


def append_equipment(payload: AppendEquipmentRequest) -> EquipmentRecord:
    """Validate and append a new equipment rental row; persists + merges into store."""
    equipment_id = payload.equipment_id.strip().upper()
    if not equipment_id:
        raise HTTPException(status_code=400, detail="Equipment ID is required")

    existing = store.get_by_id(equipment_id)
    if existing:
        raise HTTPException(
            status_code=409,
            detail=f"Equipment {equipment_id} already exists. Use Dispatch/Return to update it.",
        )

    eq_type = payload.type.strip()
    if not eq_type:
        raise HTTPException(status_code=400, detail="Equipment type is required")

    site_id = _nullish(payload.site_id)
    operator_id = _nullish(payload.last_operator_id)

    check_in = payload.check_in_date
    check_out = payload.check_out_date
    expected = payload.expected_return_date

    if check_in and check_out and check_out < check_in:
        raise HTTPException(
            status_code=400,
            detail="Check-Out (return) date cannot be before Check-In (dispatch) date.",
        )

    if payload.engine_hours_per_day is not None and payload.engine_hours_per_day < 0:
        raise HTTPException(status_code=400, detail="Engine hours cannot be negative")
    if payload.idle_hours_per_day is not None and payload.idle_hours_per_day < 0:
        raise HTTPException(status_code=400, detail="Idle hours cannot be negative")
    if payload.rental_days is not None and payload.rental_days < 0:
        raise HTTPException(status_code=400, detail="Rental days cannot be negative")

    rental_days = payload.rental_days
    if rental_days is None and check_in and check_out:
        rental_days = (check_out - check_in).days
    elif rental_days is None and check_in and expected and check_out is None:
        rental_days = (expected - check_in).days

    record = EquipmentRecord(
        equipment_id=equipment_id,
        type=eq_type,
        site_id=site_id,
        check_in_date=check_in,
        check_out_date=check_out,
        engine_hours_per_day=payload.engine_hours_per_day,
        idle_hours_per_day=payload.idle_hours_per_day,
        rental_days=rental_days,
        last_operator_id=operator_id,
        expected_return_date=expected,
    )

    # Persist for reloads
    db.upsert_manual_equipment(record)
    store.append_record(record)
    _append_local_csv(record)

    return record


def _append_local_csv(record: EquipmentRecord) -> None:
    """Also append to local CSV when using local data source (demo visibility)."""
    settings = get_settings()
    if (settings.data_source_type or "local").lower().strip() != "local":
        return
    path = Path(settings.local_csv_path)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    if not path.exists():
        return

    # Avoid duplicate CSV rows if already present
    existing = path.read_text(encoding="utf-8-sig")
    if record.equipment_id in existing.splitlines()[0:1] or any(
        line.startswith(f"{record.equipment_id},") for line in existing.splitlines()
    ):
        return

    row = [
        record.equipment_id,
        record.type,
        record.site_id or "",
        record.check_in_date.isoformat() if record.check_in_date else "",
        record.check_out_date.isoformat() if record.check_out_date else "",
        "" if record.engine_hours_per_day is None else record.engine_hours_per_day,
        "" if record.idle_hours_per_day is None else record.idle_hours_per_day,
        "" if record.rental_days is None else record.rental_days,
        record.last_operator_id or "",
        record.expected_return_date.isoformat() if record.expected_return_date else "",
    ]
    with path.open("a", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(row)
