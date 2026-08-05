"""Data source layer — local CSV or cloud CSV with polling support.

Designed so database/API/IoT sources can be added later without rewriting UI.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from pathlib import Path
from typing import Optional

import httpx

from models.schemas import DataIngestionResult, DataQualityIssue, EquipmentRecord
from services.ingestion import parse_csv_content
from utils.config import Settings, get_settings

logger = logging.getLogger(__name__)

BACKEND_ROOT = Path(__file__).resolve().parent.parent


class DataStore:
    """In-memory store backed by configurable CSV source."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._records: list[EquipmentRecord] = []
        self._issues: list[DataQualityIssue] = []
        self._last_updated: Optional[datetime] = None
        self._source: str = "uninitialized"
        self._warnings: list[str] = []
        self._last_error: Optional[str] = None
        self._overrides: dict[str, EquipmentRecord] = {}  # transaction overrides

    @property
    def last_updated(self) -> Optional[datetime]:
        return self._last_updated

    @property
    def source(self) -> str:
        return self._source

    @property
    def warnings(self) -> list[str]:
        with self._lock:
            return list(self._warnings)

    @property
    def issues(self) -> list[DataQualityIssue]:
        with self._lock:
            return list(self._issues)

    @property
    def last_error(self) -> Optional[str]:
        return self._last_error

    def get_records(self) -> list[EquipmentRecord]:
        with self._lock:
            # Apply transaction overrides on top of CSV data
            by_id = {r.equipment_id: r.model_copy(deep=True) for r in self._records}
            for eq_id, override in self._overrides.items():
                by_id[eq_id] = override.model_copy(deep=True)
            return list(by_id.values())

    def get_by_id(self, equipment_id: str) -> Optional[EquipmentRecord]:
        for r in self.get_records():
            if r.equipment_id == equipment_id:
                return r
        return None

    def upsert_override(self, record: EquipmentRecord) -> None:
        with self._lock:
            self._overrides[record.equipment_id] = record

    def append_record(self, record: EquipmentRecord) -> None:
        """Add or replace a record in the live in-memory fleet."""
        with self._lock:
            self._records = [r for r in self._records if r.equipment_id != record.equipment_id]
            self._records.append(record)
            self._overrides[record.equipment_id] = record
            self._last_updated = datetime.utcnow()

    def _merge_manual_records(self, base: list[EquipmentRecord]) -> list[EquipmentRecord]:
        """Merge SQLite manual/query-form rows on top of CSV/cloud base."""
        try:
            from services import database as db

            manual = db.list_manual_equipment()
        except Exception:
            logger.exception("Failed loading manual equipment")
            return base
        by_id = {r.equipment_id: r for r in base}
        for m in manual:
            by_id[m.equipment_id] = m
        return list(by_id.values())

    def _resolve_local_path(self, settings: Settings) -> Path:
        path = Path(settings.local_csv_path)
        if not path.is_absolute():
            path = BACKEND_ROOT / path
        return path

    def load(self, settings: Optional[Settings] = None) -> DataIngestionResult:
        settings = settings or get_settings()
        source_type = (settings.data_source_type or "local").lower().strip()

        try:
            if source_type == "cloud":
                result = self._load_cloud(settings)
            else:
                result = self._load_local(settings)
        except Exception as exc:
            logger.exception("Data load failed")
            self._last_error = str(exc)
            warning = f"Data source unavailable: {exc}"
            with self._lock:
                self._warnings = [warning]
            # Keep previous data if any
            return DataIngestionResult(
                records=self.get_records(),
                issues=[DataQualityIssue(severity="CRITICAL", message=warning)],
                source=self._source,
                loaded_at=datetime.utcnow(),
                row_count=0,
                valid_count=len(self._records),
                skipped_count=0,
            )

        merged = self._merge_manual_records(result.records)

        with self._lock:
            self._records = merged
            self._issues = result.issues
            self._last_updated = result.loaded_at
            self._source = result.source
            self._last_error = None
            self._warnings = [
                i.message for i in result.issues if i.severity in ("CRITICAL", "ERROR", "WARNING")
            ][:20]
            if result.skipped_count:
                self._warnings.insert(
                    0,
                    f"Skipped {result.skipped_count} invalid/duplicate row(s)",
                )
            manual_count = len(merged) - len(result.records)
            if manual_count > 0:
                self._warnings.insert(0, f"Merged {manual_count} query-form equipment row(s)")

        return DataIngestionResult(
            records=merged,
            issues=result.issues,
            source=result.source,
            loaded_at=result.loaded_at,
            row_count=result.row_count,
            valid_count=len(merged),
            skipped_count=result.skipped_count,
        )
    def _load_local(self, settings: Settings) -> DataIngestionResult:
        path = self._resolve_local_path(settings)
        if not path.exists():
            raise FileNotFoundError(f"Local CSV not found: {path}")
        content = path.read_text(encoding="utf-8-sig")
        return parse_csv_content(content, source=f"local:{path.name}")

    def _load_cloud(self, settings: Settings) -> DataIngestionResult:
        url = (settings.cloud_csv_url or "").strip()
        if not url:
            raise ValueError("CLOUD_CSV_URL is not configured")
        with httpx.Client(timeout=30.0, follow_redirects=True) as client:
            response = client.get(url)
            response.raise_for_status()
            content = response.text
        return parse_csv_content(content, source=f"cloud:{url[:80]}")


# Singleton store
store = DataStore()
