"""Check-In / Check-Out rental lifecycle service.

CHECK-IN  = SEND MACHINE OUT FOR RENTAL (leaves company)
CHECK-OUT = MACHINE HAS RETURNED TO COMPANY
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Optional

from fastapi import HTTPException

from models.schemas import CheckInRequest, CheckOutRequest, EquipmentRecord, RentalTransaction
from services import database as db
from services import dynamo_repo
from services.data_store import store
from utils.status import is_active_rental


def perform_check_in(payload: CheckInRequest) -> RentalTransaction:
    """Check-In: equipment leaves the company for rental."""
    if payload.expected_return_date < payload.check_in_date:
        raise HTTPException(
            status_code=400,
            detail="Expected return date cannot be before Check-In (rented out) date.",
        )

    existing = store.get_by_id(payload.equipment_id)
    if existing and is_active_rental(existing):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{payload.equipment_id} is already rented out "
                f"(Check-In {existing.check_in_date}). Check it out before a new rental."
            ),
        )

    # Sanitize text fields
    site_id = payload.site_id.strip()[:32]
    operator_id = payload.operator_id.strip()[:32]
    equipment_id = payload.equipment_id.strip()[:32]

    if existing:
        updated = existing.model_copy(deep=True)
        updated.type = existing.type
    else:
        updated = EquipmentRecord(
            equipment_id=equipment_id,
            type="Unknown",
        )

    updated.site_id = site_id
    updated.last_operator_id = operator_id
    updated.check_in_date = payload.check_in_date
    updated.check_out_date = None  # currently out
    updated.expected_return_date = payload.expected_return_date
    updated.rental_days = (payload.expected_return_date - payload.check_in_date).days
    store.upsert_override(updated)
    dynamo_repo.mirror_check_in(updated)

    tx = RentalTransaction(
        id=db.new_id("cin"),
        equipment_id=equipment_id,
        transaction_type="CHECK_IN",
        site_id=site_id,
        operator_id=operator_id,
        transaction_date=payload.check_in_date,
        expected_return_date=payload.expected_return_date,
        created_at=datetime.utcnow(),
    )
    db.save_transaction(tx)
    return tx


def perform_check_out(payload: CheckOutRequest) -> RentalTransaction:
    """Check-Out: equipment returns to the company."""
    existing = store.get_by_id(payload.equipment_id)
    if not existing:
        raise HTTPException(status_code=404, detail=f"Equipment {payload.equipment_id} not found")

    if not is_active_rental(existing):
        raise HTTPException(
            status_code=400,
            detail=(
                f"{payload.equipment_id} is not currently rented out. "
                "Check-Out only applies to equipment that has been Checked-In (sent out)."
            ),
        )

    if existing.check_in_date and payload.actual_return_date < existing.check_in_date:
        raise HTTPException(
            status_code=400,
            detail="Actual return (Check-Out) date cannot be before Check-In date.",
        )

    notes = (payload.condition_notes or "").strip()[:1000]

    updated = existing.model_copy(deep=True)
    updated.check_out_date = payload.actual_return_date
    if payload.final_engine_hours is not None:
        if payload.final_engine_hours < 0:
            raise HTTPException(status_code=400, detail="Engine hours cannot be negative")
        updated.engine_hours_per_day = payload.final_engine_hours
    if updated.check_in_date:
        updated.rental_days = (payload.actual_return_date - updated.check_in_date).days
    store.upsert_override(updated)
    dynamo_repo.mirror_check_out(payload.equipment_id, updated)

    tx = RentalTransaction(
        id=db.new_id("cout"),
        equipment_id=payload.equipment_id.strip()[:32],
        transaction_type="CHECK_OUT",
        site_id=existing.site_id,
        operator_id=existing.last_operator_id,
        transaction_date=payload.actual_return_date,
        engine_hours=payload.final_engine_hours,
        condition_notes=notes or None,
        created_at=datetime.utcnow(),
    )
    db.save_transaction(tx)
    return tx


def rental_history(equipment_id: Optional[str] = None) -> list[RentalTransaction]:
    txs = db.list_transactions(equipment_id=equipment_id)

    # Also synthesize history from CSV completed rentals for demo richness
    synthetic: list[RentalTransaction] = []
    for r in store.get_records():
        if equipment_id and r.equipment_id != equipment_id:
            continue
        if r.check_in_date:
            synthetic.append(
                RentalTransaction(
                    id=f"hist_in_{r.equipment_id}_{r.check_in_date}",
                    equipment_id=r.equipment_id,
                    transaction_type="CHECK_IN",
                    site_id=r.site_id,
                    operator_id=r.last_operator_id,
                    transaction_date=r.check_in_date,
                    expected_return_date=r.expected_return_date or r.check_out_date,
                    created_at=datetime.combine(r.check_in_date, datetime.min.time()),
                )
            )
        if r.check_out_date:
            synthetic.append(
                RentalTransaction(
                    id=f"hist_out_{r.equipment_id}_{r.check_out_date}",
                    equipment_id=r.equipment_id,
                    transaction_type="CHECK_OUT",
                    site_id=r.site_id,
                    operator_id=r.last_operator_id,
                    transaction_date=r.check_out_date,
                    engine_hours=r.engine_hours_per_day,
                    created_at=datetime.combine(r.check_out_date, datetime.min.time()),
                )
            )

    # Prefer real transactions; merge unique
    by_id = {t.id: t for t in synthetic}
    for t in txs:
        by_id[t.id] = t
    merged = list(by_id.values())
    merged.sort(key=lambda t: (t.transaction_date, t.created_at), reverse=True)
    return merged
