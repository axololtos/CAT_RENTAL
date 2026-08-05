"""14-day equipment demand forecast (site x equipment type) using XGBoost.

Trains on historical rental check-ins, either the local prototype CSV
(backend/data/equipment_rentals.csv) or Parquet objects pulled from the
telemetry data lake (s3://cat-rentals-telemetry-lake-<account>-<region>/telemetry/).

Usage:
    python demand_forecast.py --input ../../backend/data/equipment_rentals.csv
    python demand_forecast.py --s3-uri s3://cat-rentals-telemetry-lake-123456789012-us-east-1/telemetry/

Output:
    - Trained model saved to model_demand_forecast.json
    - forecast_14d.csv with predicted demand per site x equipment type
"""
import argparse

import boto3
import pandas as pd
from xgboost import XGBRegressor

FORECAST_HORIZON_DAYS = 14
LOOKBACK_WEEKS = 8


def load_local_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(
        columns={
            "Equipment ID": "equipment_id",
            "Type": "equipment_type",
            "Site ID": "site_id",
            "Check-In Date": "checkin_date",
        }
    )
    df["checkin_date"] = pd.to_datetime(df["checkin_date"], errors="coerce")
    return df.dropna(subset=["checkin_date", "site_id", "equipment_type"])


def load_s3_parquet(s3_uri: str) -> pd.DataFrame:
    s3 = boto3.client("s3")
    bucket, _, prefix = s3_uri.replace("s3://", "").partition("/")
    paginator = s3.get_paginator("list_objects_v2")
    frames = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith(".parquet"):
                continue
            local_buf = s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            frames.append(pd.read_parquet(pd.io.common.BytesIO(local_buf)))
    if not frames:
        raise ValueError(f"No Parquet objects found under {s3_uri}")
    df = pd.concat(frames, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.rename(columns={"timestamp": "checkin_date"})
    return df.dropna(subset=["checkin_date", "site_id", "equipment_type"])


def build_weekly_demand(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["week"] = df["checkin_date"].dt.to_period("W").dt.start_time
    weekly = (
        df.groupby(["site_id", "equipment_type", "week"])
        .size()
        .reset_index(name="demand")
        .sort_values(["site_id", "equipment_type", "week"])
    )
    return weekly


def add_lag_features(weekly: pd.DataFrame) -> pd.DataFrame:
    weekly = weekly.copy()
    grouped = weekly.groupby(["site_id", "equipment_type"])["demand"]
    for lag in range(1, LOOKBACK_WEEKS + 1):
        weekly[f"lag_{lag}"] = grouped.shift(lag)
    weekly["rolling_mean_4"] = grouped.transform(lambda s: s.shift(1).rolling(4).mean())
    weekly["site_id_code"] = weekly["site_id"].astype("category").cat.codes
    weekly["equipment_type_code"] = weekly["equipment_type"].astype("category").cat.codes
    return weekly.dropna()


def train(weekly: pd.DataFrame) -> tuple[XGBRegressor, float]:
    feature_cols = [c for c in weekly.columns if c.startswith("lag_")] + [
        "rolling_mean_4",
        "site_id_code",
        "equipment_type_code",
    ]

    split_idx = int(len(weekly) * 0.8)  # time-ordered split, no shuffling
    train_df = weekly.iloc[:split_idx]
    test_df = weekly.iloc[split_idx:]

    model = XGBRegressor(
        n_estimators=300,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        objective="reg:squarederror",
    )
    model.fit(train_df[feature_cols], train_df["demand"])

    if len(test_df) > 0:
        preds = model.predict(test_df[feature_cols])
        mae = float((preds - test_df["demand"]).abs().mean())
    else:
        mae = float("nan")

    return model, mae


def forecast_next_period(model: XGBRegressor, weekly: pd.DataFrame) -> pd.DataFrame:
    feature_cols = [c for c in weekly.columns if c.startswith("lag_")] + [
        "rolling_mean_4",
        "site_id_code",
        "equipment_type_code",
    ]
    latest = weekly.sort_values("week").groupby(["site_id", "equipment_type"]).tail(1)
    latest = latest.copy()
    latest["predicted_demand_next_period"] = model.predict(latest[feature_cols])
    latest["forecast_horizon_days"] = FORECAST_HORIZON_DAYS
    return latest[
        ["site_id", "equipment_type", "predicted_demand_next_period", "forecast_horizon_days"]
    ]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Path to local equipment_rentals.csv")
    parser.add_argument("--s3-uri", help="s3://bucket/prefix/ of Parquet telemetry")
    parser.add_argument("--output", default="forecast_14d.csv")
    parser.add_argument("--model-output", default="model_demand_forecast.json")
    args = parser.parse_args()

    if args.s3_uri:
        df = load_s3_parquet(args.s3_uri)
    elif args.input:
        df = load_local_csv(args.input)
    else:
        parser.error("Provide either --input or --s3-uri")

    weekly = build_weekly_demand(df)
    weekly = add_lag_features(weekly)

    if weekly.empty:
        raise SystemExit(
            f"Not enough history to build lag features "
            f"(need >= {LOOKBACK_WEEKS + 1} weeks per site/equipment-type pair)."
        )

    model, mae = train(weekly)
    print(f"Validation MAE: {mae:.3f}")

    forecast = forecast_next_period(model, weekly)
    forecast.to_csv(args.output, index=False)
    model.save_model(args.model_output)
    print(f"Saved forecast to {args.output} and model to {args.model_output}")


if __name__ == "__main__":
    main()
