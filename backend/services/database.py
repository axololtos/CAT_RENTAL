"""SQLite persistence for check-in / check-out transactions and notifications."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from models.schemas import Alert, RentalTransaction
from utils.config import get_settings

BACKEND_ROOT = Path(__file__).resolve().parent.parent


def _db_path() -> Path:
    settings = get_settings()
    path = Path(settings.sqlite_path)
    if not path.is_absolute():
        path = BACKEND_ROOT / path
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_db_path()), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    conn = get_connection()
    try:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS rental_transactions (
                id TEXT PRIMARY KEY,
                equipment_id TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                site_id TEXT,
                operator_id TEXT,
                transaction_date TEXT NOT NULL,
                expected_return_date TEXT,
                engine_hours REAL,
                condition_notes TEXT,
                created_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS notifications (
                id TEXT PRIMARY KEY,
                equipment_id TEXT,
                category TEXT NOT NULL,
                severity TEXT NOT NULL,
                title TEXT NOT NULL,
                message TEXT NOT NULL,
                detected_at TEXT NOT NULL,
                read INTEGER DEFAULT 0,
                metadata TEXT DEFAULT '{}'
            );

            CREATE TABLE IF NOT EXISTS manual_equipment (
                equipment_id TEXT PRIMARY KEY,
                type TEXT NOT NULL,
                site_id TEXT,
                check_in_date TEXT,
                check_out_date TEXT,
                engine_hours_per_day REAL,
                idle_hours_per_day REAL,
                rental_days INTEGER,
                last_operator_id TEXT,
                expected_return_date TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def save_transaction(tx: RentalTransaction) -> RentalTransaction:
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO rental_transactions
            (id, equipment_id, transaction_type, site_id, operator_id,
             transaction_date, expected_return_date, engine_hours, condition_notes, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                tx.id,
                tx.equipment_id,
                tx.transaction_type,
                tx.site_id,
                tx.operator_id,
                tx.transaction_date.isoformat(),
                tx.expected_return_date.isoformat() if tx.expected_return_date else None,
                tx.engine_hours,
                tx.condition_notes,
                tx.created_at.isoformat(),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return tx


def list_transactions(
    equipment_id: Optional[str] = None,
    limit: int = 200,
) -> list[RentalTransaction]:
    conn = get_connection()
    try:
        if equipment_id:
            rows = conn.execute(
                """
                SELECT * FROM rental_transactions
                WHERE equipment_id = ?
                ORDER BY created_at DESC LIMIT ?
                """,
                (equipment_id, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                """
                SELECT * FROM rental_transactions
                ORDER BY created_at DESC LIMIT ?
                """,
                (limit,),
            ).fetchall()
        return [_row_to_tx(r) for r in rows]
    finally:
        conn.close()


def _row_to_tx(row: sqlite3.Row) -> RentalTransaction:
    return RentalTransaction(
        id=row["id"],
        equipment_id=row["equipment_id"],
        transaction_type=row["transaction_type"],
        site_id=row["site_id"],
        operator_id=row["operator_id"],
        transaction_date=date.fromisoformat(row["transaction_date"]),
        expected_return_date=(
            date.fromisoformat(row["expected_return_date"]) if row["expected_return_date"] else None
        ),
        engine_hours=row["engine_hours"],
        condition_notes=row["condition_notes"],
        created_at=datetime.fromisoformat(row["created_at"]),
    )


def upsert_notifications(alerts: list[Alert]) -> None:
    """Replace generated notifications while preserving read state for same IDs."""
    conn = get_connection()
    try:
        existing = {
            r["id"]: r["read"]
            for r in conn.execute("SELECT id, read FROM notifications").fetchall()
        }
        # Keep user-only notifications? For prototype, regenerate from engine.
        # Preserve read flags for matching IDs.
        conn.execute("DELETE FROM notifications")
        for a in alerts:
            read = existing.get(a.id, 0 if not a.read else 1)
            conn.execute(
                """
                INSERT INTO notifications
                (id, equipment_id, category, severity, title, message, detected_at, read, metadata)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    a.id,
                    a.equipment_id,
                    a.category.value,
                    a.severity.value,
                    a.title,
                    a.message,
                    a.detected_at.isoformat(),
                    read,
                    json.dumps(a.metadata),
                ),
            )
        conn.commit()
    finally:
        conn.close()


def list_notifications(
    category: Optional[str] = None,
    severity: Optional[str] = None,
    equipment_id: Optional[str] = None,
    unread_only: bool = False,
) -> list[Alert]:
    conn = get_connection()
    try:
        query = "SELECT * FROM notifications WHERE 1=1"
        params: list = []
        if category:
            query += " AND category = ?"
            params.append(category)
        if severity:
            query += " AND severity = ?"
            params.append(severity)
        if equipment_id:
            query += " AND equipment_id = ?"
            params.append(equipment_id)
        if unread_only:
            query += " AND read = 0"
        query += " ORDER BY detected_at DESC"
        rows = conn.execute(query, params).fetchall()
        return [_row_to_alert(r) for r in rows]
    finally:
        conn.close()


def mark_notification_read(notification_id: str, read: bool = True) -> bool:
    conn = get_connection()
    try:
        cur = conn.execute(
            "UPDATE notifications SET read = ? WHERE id = ?",
            (1 if read else 0, notification_id),
        )
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def _row_to_alert(row: sqlite3.Row) -> Alert:
    from models.schemas import AlertCategory, AlertSeverity

    return Alert(
        id=row["id"],
        equipment_id=row["equipment_id"],
        category=AlertCategory(row["category"]),
        severity=AlertSeverity(row["severity"]),
        title=row["title"],
        message=row["message"],
        detected_at=datetime.fromisoformat(row["detected_at"]),
        read=bool(row["read"]),
        metadata=json.loads(row["metadata"] or "{}"),
    )


def new_id(prefix: str = "tx") -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def upsert_manual_equipment(record: "EquipmentRecord") -> None:
    from models.schemas import EquipmentRecord  # noqa: F401

    now = datetime.utcnow().isoformat()
    conn = get_connection()
    try:
        conn.execute(
            """
            INSERT INTO manual_equipment (
                equipment_id, type, site_id, check_in_date, check_out_date,
                engine_hours_per_day, idle_hours_per_day, rental_days,
                last_operator_id, expected_return_date, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(equipment_id) DO UPDATE SET
                type=excluded.type,
                site_id=excluded.site_id,
                check_in_date=excluded.check_in_date,
                check_out_date=excluded.check_out_date,
                engine_hours_per_day=excluded.engine_hours_per_day,
                idle_hours_per_day=excluded.idle_hours_per_day,
                rental_days=excluded.rental_days,
                last_operator_id=excluded.last_operator_id,
                expected_return_date=excluded.expected_return_date,
                updated_at=excluded.updated_at
            """,
            (
                record.equipment_id,
                record.type,
                record.site_id,
                record.check_in_date.isoformat() if record.check_in_date else None,
                record.check_out_date.isoformat() if record.check_out_date else None,
                record.engine_hours_per_day,
                record.idle_hours_per_day,
                record.rental_days,
                record.last_operator_id,
                record.expected_return_date.isoformat() if record.expected_return_date else None,
                now,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def list_manual_equipment() -> list:
    from models.schemas import EquipmentRecord

    conn = get_connection()
    try:
        rows = conn.execute("SELECT * FROM manual_equipment ORDER BY updated_at DESC").fetchall()
        out = []
        for row in rows:
            out.append(
                EquipmentRecord(
                    equipment_id=row["equipment_id"],
                    type=row["type"],
                    site_id=row["site_id"] or None,
                    check_in_date=date.fromisoformat(row["check_in_date"]) if row["check_in_date"] else None,
                    check_out_date=date.fromisoformat(row["check_out_date"]) if row["check_out_date"] else None,
                    engine_hours_per_day=row["engine_hours_per_day"],
                    idle_hours_per_day=row["idle_hours_per_day"],
                    rental_days=row["rental_days"],
                    last_operator_id=row["last_operator_id"] or None,
                    expected_return_date=(
                        date.fromisoformat(row["expected_return_date"])
                        if row["expected_return_date"]
                        else None
                    ),
                )
            )
        return out
    finally:
        conn.close()
