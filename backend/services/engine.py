"""Application engine — orchestrates enrichment, anomalies, alerts, forecasts."""

from __future__ import annotations

import logging
import threading
from datetime import datetime
from typing import Optional

from ml.anomaly_detector import detect_ml_anomalies
from ml.forecasting import run_forecast
from models.schemas import Anomaly, ForecastResult, Recommendation
from services.alerts import anomalies_to_alerts, generate_return_alerts
from services.analytics import enrich_fleet
from services import database as db
from services.data_store import store
from services.recommendations import generate_recommendations
from services.rule_anomalies import detect_rule_anomalies
from utils.config import Settings, get_settings

logger = logging.getLogger(__name__)


class AppEngine:
    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._anomalies: list[Anomaly] = []
        self._forecast: Optional[ForecastResult] = None
        self._recommendations: list[Recommendation] = []
        self._settings_overrides: dict = {}

    def effective_settings(self) -> Settings:
        base = get_settings()
        if not self._settings_overrides:
            return base
        data = base.model_dump()
        data.update({k: v for k, v in self._settings_overrides.items() if v is not None})
        return Settings(**data)

    def update_settings(self, updates: dict) -> Settings:
        with self._lock:
            for k, v in updates.items():
                if v is not None:
                    self._settings_overrides[k] = v
            # Clear settings cache so env-based defaults still work for unset keys
            get_settings.cache_clear()
            return self.effective_settings()

    def get_settings_public(self) -> dict:
        s = self.effective_settings()
        return {
            "data_source_type": s.data_source_type,
            "cloud_csv_url": s.cloud_csv_url,
            "refresh_interval_seconds": s.refresh_interval_seconds,
            "util_low_max": s.util_low_max,
            "util_moderate_max": s.util_moderate_max,
            "util_good_max": s.util_good_max,
            "idle_hours_anomaly_threshold": s.idle_hours_anomaly_threshold,
            "due_soon_days": s.due_soon_days,
            "forecast_horizon_days": s.forecast_horizon_days,
            "use_demo_forecast_data": s.use_demo_forecast_data,
            "min_forecast_records": s.min_forecast_records,
        }

    def refresh(self, retrain_forecast: bool = True) -> dict:
        settings = self.effective_settings()
        result = store.load(settings)
        records = store.get_records()

        rule_anoms = detect_rule_anomalies(records, settings)
        ml_anoms = detect_ml_anomalies(records)
        all_anoms = rule_anoms + ml_anoms

        anomaly_ids = {a.equipment_id for a in all_anoms}
        enriched = enrich_fleet(records, anomaly_ids)

        # Push enriched derived fields back via overrides carefully —
        # we keep enrichment ephemeral for reads
        return_alerts = generate_return_alerts(enriched, settings)
        anom_alerts = anomalies_to_alerts(
            [a for a in all_anoms if a.severity.value in ("CRITICAL", "WARNING", "URGENT")]
        )
        # Data source warnings as alerts
        data_alerts = []
        from models.schemas import Alert, AlertCategory, AlertSeverity

        if store.last_error:
            data_alerts.append(
                Alert(
                    id="data_source_error",
                    category=AlertCategory.DATA_SOURCE_ERROR,
                    severity=AlertSeverity.CRITICAL,
                    title="Data source error",
                    message=store.last_error,
                    detected_at=datetime.utcnow(),
                )
            )

        all_alerts = return_alerts + anom_alerts[:30] + data_alerts
        db.upsert_notifications(all_alerts)

        forecast = self._forecast
        if retrain_forecast or forecast is None:
            forecast = run_forecast(enriched, settings)

        recommendations = generate_recommendations(enriched, all_anoms, forecast.items if forecast else [])

        with self._lock:
            self._anomalies = all_anoms
            self._forecast = forecast
            self._recommendations = recommendations

        return {
            "loaded": result.valid_count,
            "skipped": result.skipped_count,
            "issues": len(result.issues),
            "anomalies": len(all_anoms),
            "alerts": len(all_alerts),
            "last_updated": store.last_updated.isoformat() if store.last_updated else None,
            "source": store.source,
        }

    def get_enriched_records(self) -> list:
        records = store.get_records()
        anomaly_ids = {a.equipment_id for a in self._anomalies}
        # Apply ML flags from cached anomalies
        ml_scores = {
            a.equipment_id: a.anomaly_score
            for a in self._anomalies
            if a.source.value == "ML"
        }
        for r in records:
            if r.equipment_id in ml_scores:
                r.is_ml_anomaly = True
                r.ml_anomaly_score = ml_scores[r.equipment_id]
        return enrich_fleet(records, anomaly_ids)

    @property
    def anomalies(self) -> list[Anomaly]:
        return list(self._anomalies)

    @property
    def forecast(self) -> Optional[ForecastResult]:
        return self._forecast

    @property
    def recommendations(self) -> list[Recommendation]:
        return list(self._recommendations)


engine = AppEngine()
