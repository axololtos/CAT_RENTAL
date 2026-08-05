"""Demand forecasting pipeline.

Time-aware train/test split. Evaluates moving-average baseline vs Random Forest
(and GradientBoosting if available). Never invents fake accuracy.
"""

from __future__ import annotations

import logging
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Optional

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor, RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.preprocessing import LabelEncoder

from models.schemas import EquipmentRecord, ForecastItem, ForecastResult
from utils.config import Settings, get_settings

logger = logging.getLogger(__name__)


def _generate_demo_history(base_records: list[EquipmentRecord]) -> list[dict]:
    """Synthetic historical rental events for DEMO MODE only — clearly separated."""
    rng = np.random.default_rng(42)
    types = sorted({r.type for r in base_records if r.type}) or ["Excavator", "Bulldozer", "Crane"]
    sites = sorted({r.site_id for r in base_records if r.site_id}) or ["S001", "S002", "S003"]

    events = []
    start = date.today() - timedelta(days=180)
    for day_offset in range(180):
        d = start + timedelta(days=day_offset)
        for site in sites:
            for eq_type in types:
                # Seasonal-ish demand
                base = 0.3 + 0.2 * np.sin(day_offset / 14)
                if eq_type == "Excavator":
                    base += 0.4
                count = int(rng.poisson(max(0.1, base)))
                for _ in range(count):
                    events.append(
                        {
                            "date": d,
                            "site_id": site,
                            "equipment_type": eq_type,
                        }
                    )
    return events


def _extract_events(records: list[EquipmentRecord]) -> list[dict]:
    events = []
    for r in records:
        if r.check_in_date is None:
            continue
        events.append(
            {
                "date": r.check_in_date,
                "site_id": r.site_id or "UNKNOWN",
                "equipment_type": r.type or "Unknown",
            }
        )
    return events


def _aggregate_weekly(events: list[dict]) -> list[dict]:
    """Aggregate to weekly counts per site × type."""
    buckets: dict[tuple, int] = defaultdict(int)
    for e in events:
        d: date = e["date"]
        week_start = d - timedelta(days=d.weekday())
        key = (week_start, e["site_id"], e["equipment_type"])
        buckets[key] += 1

    rows = []
    for (week_start, site, eq_type), count in sorted(buckets.items()):
        rows.append(
            {
                "week_start": week_start,
                "site_id": site,
                "equipment_type": eq_type,
                "count": count,
            }
        )
    return rows


def _demand_level(value: float) -> str:
    if value < 0.5:
        return "LOW"
    if value < 1.5:
        return "MEDIUM"
    return "HIGH"


def run_forecast(
    records: list[EquipmentRecord],
    settings: Optional[Settings] = None,
    horizon_days: Optional[int] = None,
) -> ForecastResult:
    s = settings or get_settings()
    horizon = horizon_days or s.forecast_horizon_days
    now = datetime.utcnow()

    events = _extract_events(records)
    demo_mode = False

    if len(events) < s.min_forecast_records:
        if s.use_demo_forecast_data:
            events = _generate_demo_history(records)
            demo_mode = True
        else:
            return ForecastResult(
                items=[],
                model_name="none",
                mae=None,
                rmse=None,
                sufficient_data=False,
                message=(
                    "Insufficient historical data for reliable ML forecasting. "
                    f"Need at least {s.min_forecast_records} rental events with Check-In dates "
                    f"(found {len(events)}). Enable demo forecast data in Settings to preview "
                    "the forecasting architecture with generated sample history."
                ),
                demo_mode=False,
                horizon_days=horizon,
                generated_at=now,
            )

    weekly = _aggregate_weekly(events)
    if len(weekly) < 8:
        return ForecastResult(
            items=[],
            model_name="none",
            sufficient_data=False,
            message=(
                "Insufficient historical data for reliable ML forecasting. "
                "Not enough weekly aggregates after grouping by site and equipment type."
            ),
            demo_mode=demo_mode,
            horizon_days=horizon,
            generated_at=now,
        )

    # Build panel features
    site_le = LabelEncoder()
    type_le = LabelEncoder()
    sites = [r["site_id"] for r in weekly]
    types = [r["equipment_type"] for r in weekly]
    site_enc = site_le.fit_transform(sites)
    type_enc = type_le.fit_transform(types)

    min_week = min(r["week_start"] for r in weekly)
    X_list = []
    y_list = []
    meta = []
    for i, row in enumerate(weekly):
        week_num = (row["week_start"] - min_week).days // 7
        X_list.append([week_num, site_enc[i], type_enc[i], row["week_start"].month])
        y_list.append(row["count"])
        meta.append(row)

    X = np.array(X_list, dtype=float)
    y = np.array(y_list, dtype=float)

    # Time-aware split (last 20% of weeks for test)
    order = np.argsort(X[:, 0])
    X = X[order]
    y = y[order]
    meta = [meta[i] for i in order]

    split = max(1, int(len(X) * 0.8))
    if split >= len(X):
        split = len(X) - 1

    X_train, X_test = X[:split], X[split:]
    y_train, y_test = y[:split], y[split:]

    candidates = {}

    # Moving average baseline (per site-type mean of train)
    train_means: dict[tuple, list] = defaultdict(list)
    for features, target, m in zip(X_train, y_train, meta[:split]):
        train_means[(m["site_id"], m["equipment_type"])].append(float(target))
    global_mean = float(np.mean(y_train)) if len(y_train) else 0.0

    ma_preds = []
    for m in meta[split:]:
        key = (m["site_id"], m["equipment_type"])
        vals = train_means.get(key, [])
        ma_preds.append(float(np.mean(vals)) if vals else global_mean)
    ma_preds_arr = np.array(ma_preds)
    if len(y_test):
        candidates["moving_average"] = {
            "mae": float(mean_absolute_error(y_test, ma_preds_arr)),
            "rmse": float(np.sqrt(mean_squared_error(y_test, ma_preds_arr))),
            "predict_fn": None,
            "kind": "ma",
        }

    # Random Forest
    try:
        rf = RandomForestRegressor(n_estimators=80, random_state=42, max_depth=6)
        rf.fit(X_train, y_train)
        rf_pred = rf.predict(X_test) if len(X_test) else np.array([])
        if len(y_test):
            candidates["random_forest"] = {
                "mae": float(mean_absolute_error(y_test, rf_pred)),
                "rmse": float(np.sqrt(mean_squared_error(y_test, rf_pred))),
                "model": rf,
                "kind": "sklearn",
            }
    except Exception:
        logger.exception("Random Forest training failed")

    # Gradient Boosting
    try:
        gb = GradientBoostingRegressor(n_estimators=80, random_state=42, max_depth=3)
        gb.fit(X_train, y_train)
        gb_pred = gb.predict(X_test) if len(X_test) else np.array([])
        if len(y_test):
            candidates["gradient_boosting"] = {
                "mae": float(mean_absolute_error(y_test, gb_pred)),
                "rmse": float(np.sqrt(mean_squared_error(y_test, gb_pred))),
                "model": gb,
                "kind": "sklearn",
            }
    except Exception:
        logger.exception("Gradient Boosting training failed")

    if not candidates:
        return ForecastResult(
            items=[],
            model_name="none",
            sufficient_data=False,
            message="Forecast model training failed.",
            demo_mode=demo_mode,
            horizon_days=horizon,
            generated_at=now,
        )

    # Prefer sklearn models when the holdout set is tiny or MA MAE is
    # suspiciously perfect (common with sparse weekly counts of 1).
    def _rank(name: str) -> tuple:
        c = candidates[name]
        preference = 0 if name != "moving_average" else 1
        if len(y_test) < 3 and name == "moving_average":
            preference = 2
        if c["mae"] == 0.0 and name == "moving_average" and "random_forest" in candidates:
            preference = 2
        return (preference, c["mae"], c["rmse"])

    best_name = min(candidates.keys(), key=_rank)
    best = candidates[best_name]

    # Forecast next horizon (weekly steps)
    weeks_ahead = max(1, (horizon + 6) // 7)
    last_week_num = int(X[-1, 0])
    today = date.today()
    next_monday = today + timedelta(days=(7 - today.weekday()) % 7)

    unique_sites = list(site_le.classes_)
    unique_types = list(type_le.classes_)
    items: list[ForecastItem] = []

    for w in range(1, weeks_ahead + 1):
        week_start = next_monday + timedelta(days=7 * (w - 1))
        week_end = week_start + timedelta(days=6)
        week_num = last_week_num + w
        for site in unique_sites:
            if site == "UNKNOWN":
                continue
            for eq_type in unique_types:
                feats = np.array(
                    [[week_num, site_le.transform([site])[0], type_le.transform([eq_type])[0], week_start.month]],
                    dtype=float,
                )
                if best["kind"] == "ma":
                    vals = train_means.get((site, eq_type), [])
                    pred = float(np.mean(vals)) if vals else global_mean
                else:
                    pred = float(best["model"].predict(feats)[0])
                pred = max(0.0, round(pred, 2))
                items.append(
                    ForecastItem(
                        equipment_type=eq_type,
                        site_id=site,
                        period_start=week_start,
                        period_end=week_end,
                        predicted_demand=pred,
                        demand_level=_demand_level(pred),
                        confidence="moderate" if not demo_mode else "demo",
                        model_name=best_name,
                    )
                )

    # Aggregate to horizon summary (sum over weeks) for cleaner UI — top-level period
    summary: dict[tuple, list[ForecastItem]] = defaultdict(list)
    for item in items:
        # Split 7-day vs 30-day groups by week index
        summary[(item.equipment_type, item.site_id)].append(item)

    horizon_items: list[ForecastItem] = []
    period_end = today + timedelta(days=horizon)
    for (eq_type, site), group in summary.items():
        # Use weeks within horizon
        relevant = [g for g in group if g.period_start <= period_end]
        if not relevant:
            relevant = group[:1]
        avg_demand = float(np.mean([g.predicted_demand for g in relevant]))
        horizon_items.append(
            ForecastItem(
                equipment_type=eq_type,
                site_id=site,
                period_start=today,
                period_end=period_end,
                predicted_demand=round(avg_demand, 2),
                demand_level=_demand_level(avg_demand),
                confidence="moderate" if not demo_mode else "demo-only",
                model_name=best_name,
            )
        )

    horizon_items.sort(key=lambda x: (-x.predicted_demand, x.equipment_type, x.site_id))

    msg = (
        f"Forecast generated using {best_name} "
        f"(validation MAE={best['mae']:.3f}, RMSE={best['rmse']:.3f})."
    )
    if len(y_test) < 5:
        msg += (
            f" Note: holdout set is small (n={len(y_test)}); "
            "validation metrics have limited statistical reliability."
        )
    if demo_mode:
        msg = (
            "DEMO MODE: using generated historical sample data — "
            "NOT mixed with production rental records. " + msg
        )

    return ForecastResult(
        items=horizon_items,
        model_name=best_name,
        mae=best["mae"],
        rmse=best["rmse"],
        sufficient_data=True,
        message=msg,
        demo_mode=demo_mode,
        horizon_days=horizon,
        generated_at=now,
    )
