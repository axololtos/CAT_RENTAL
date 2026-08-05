"""Isolation Forest ML anomaly detection.

Results are labeled as "Potential anomaly" — not definitive misuse.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Optional

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import LabelEncoder, StandardScaler

from models.schemas import AlertSeverity, Anomaly, AnomalySource, EquipmentRecord
from services.database import new_id
from utils.status import calculate_utilization

logger = logging.getLogger(__name__)

MIN_SAMPLES = 8


def detect_ml_anomalies(records: list[EquipmentRecord]) -> list[Anomaly]:
    """Run Isolation Forest on equipment usage features."""
    now = datetime.utcnow()

    if len(records) < MIN_SAMPLES:
        logger.info("Insufficient samples for Isolation Forest (%s < %s)", len(records), MIN_SAMPLES)
        return []

    feature_rows = []
    valid_records: list[EquipmentRecord] = []
    types: list[str] = []

    for rec in records:
        engine = rec.engine_hours_per_day if rec.engine_hours_per_day is not None else 0.0
        idle = rec.idle_hours_per_day if rec.idle_hours_per_day is not None else 0.0
        rental = rec.rental_days if rec.rental_days is not None else 0
        util = calculate_utilization(
            rec.engine_hours_per_day if rec.engine_hours_per_day is not None else 0.0,
            rec.idle_hours_per_day if rec.idle_hours_per_day is not None else 0.0,
        )
        util = util if util is not None else 0.0
        feature_rows.append([engine, idle, float(rental), util])
        valid_records.append(rec)
        types.append(rec.type or "Unknown")

    X = np.array(feature_rows, dtype=float)

    # Encode equipment type
    le = LabelEncoder()
    type_encoded = le.fit_transform(types).reshape(-1, 1)
    X = np.hstack([X, type_encoded.astype(float)])

    # Site presence flag
    site_flag = np.array(
        [[0.0 if r.site_id is None else 1.0] for r in valid_records],
        dtype=float,
    )
    X = np.hstack([X, site_flag])

    try:
        scaler = StandardScaler()
        X_scaled = scaler.fit_transform(X)

        # contamination: expect a modest outlier fraction
        contamination = min(0.2, max(0.05, 2.0 / len(records)))
        model = IsolationForest(
            n_estimators=100,
            contamination=contamination,
            random_state=42,
        )
        preds = model.fit_predict(X_scaled)
        scores = model.decision_function(X_scaled)  # lower = more anomalous
    except Exception:
        logger.exception("Isolation Forest failed")
        return []

    anomalies: list[Anomaly] = []
    for rec, pred, score in zip(valid_records, preds, scores):
        if pred == -1:
            # Convert score to a 0-1-ish anomaly magnitude (higher = more anomalous)
            anomaly_score = round(float(-score), 4)
            anomalies.append(
                Anomaly(
                    id=new_id("ml"),
                    equipment_id=rec.equipment_id,
                    source=AnomalySource.ML,
                    severity=AlertSeverity.WARNING,
                    reason=(
                        f"Potential anomaly detected by Isolation Forest "
                        f"(score={anomaly_score}). Review usage pattern — "
                        "this is not confirmed misuse."
                    ),
                    detected_at=now,
                    relevant_values={
                        "engine_hours_per_day": rec.engine_hours_per_day,
                        "idle_hours_per_day": rec.idle_hours_per_day,
                        "rental_days": rec.rental_days,
                        "utilization_pct": calculate_utilization(
                            rec.engine_hours_per_day, rec.idle_hours_per_day
                        ),
                    },
                    anomaly_score=anomaly_score,
                )
            )
            rec.is_ml_anomaly = True
            rec.ml_anomaly_score = anomaly_score

    return anomalies
