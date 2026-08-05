"""Unsupervised anomaly detection over fleet telemetry using Isolation Forest.

Flags equipment behaving statistically unlike the rest of the fleet, with an
explicit rule overlay for two known high-risk patterns that are worth naming
even when they don't stand out in the unsupervised score:

  - CONTINUOUS_OVERUSE  engine_hours_today >= 18 (near-continuous operation)
  - OFF_HOURS_ACTIVITY  meaningful engine usage between 22:00 and 05:00

Usage:
    python isolation_forest_anomaly.py --input ../../backend/data/equipment_rentals.csv
    python isolation_forest_anomaly.py --s3-uri s3://cat-rentals-telemetry-lake-<account>-<region>/telemetry/
"""
import argparse

import boto3
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

CONTINUOUS_OVERUSE_HOURS = 18.0
OFF_HOURS_START = 22
OFF_HOURS_END = 5
OFF_HOURS_MIN_ENGINE_HOURS = 1.0

FEATURE_COLUMNS = ["engine_hours_today", "idle_hours_today", "utilization_pct", "hour_of_day"]


def load_local_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    df = df.rename(
        columns={
            "Equipment ID": "equipment_id",
            "Engine Hours/Day": "engine_hours_today",
            "Idle Hours/Day": "idle_hours_today",
            "Check-In Date": "timestamp",
        }
    )
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    return df.dropna(subset=["timestamp", "equipment_id"])


def load_s3_parquet(s3_uri: str) -> pd.DataFrame:
    s3 = boto3.client("s3")
    bucket, _, prefix = s3_uri.replace("s3://", "").partition("/")
    paginator = s3.get_paginator("list_objects_v2")
    frames = []
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get("Contents", []):
            if not obj["Key"].endswith(".parquet"):
                continue
            body = s3.get_object(Bucket=bucket, Key=obj["Key"])["Body"].read()
            frames.append(pd.read_parquet(pd.io.common.BytesIO(body)))
    if not frames:
        raise ValueError(f"No Parquet objects found under {s3_uri}")
    df = pd.concat(frames, ignore_index=True)
    df["timestamp"] = pd.to_datetime(df["timestamp"], errors="coerce")
    df = df.rename(columns={"engine_hours_today": "engine_hours_today", "idle_hours_today": "idle_hours_today"})
    return df.dropna(subset=["timestamp", "equipment_id"])


def engineer_features(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["engine_hours_today"] = df.get("engine_hours_today", 0).fillna(0)
    df["idle_hours_today"] = df.get("idle_hours_today", 0).fillna(0)
    total = df["engine_hours_today"] + df["idle_hours_today"]
    df["utilization_pct"] = (df["engine_hours_today"] / total.replace(0, pd.NA) * 100).fillna(0)
    df["hour_of_day"] = df["timestamp"].dt.hour
    return df


def apply_rule_overlay(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df["rule_continuous_overuse"] = df["engine_hours_today"] >= CONTINUOUS_OVERUSE_HOURS

    is_off_hours = (df["hour_of_day"] >= OFF_HOURS_START) | (df["hour_of_day"] < OFF_HOURS_END)
    df["rule_off_hours_activity"] = is_off_hours & (df["engine_hours_today"] >= OFF_HOURS_MIN_ENGINE_HOURS)

    return df


def run_isolation_forest(df: pd.DataFrame, contamination: float = 0.05) -> pd.DataFrame:
    df = df.copy()
    scaler = StandardScaler()
    X = scaler.fit_transform(df[FEATURE_COLUMNS])

    model = IsolationForest(
        n_estimators=200,
        contamination=contamination,
        random_state=42,
    )
    df["ml_anomaly_score"] = model.fit_predict(X)  # -1 = anomaly, 1 = normal
    df["is_ml_anomaly"] = df["ml_anomaly_score"] == -1
    return df


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", help="Path to local equipment_rentals.csv")
    parser.add_argument("--s3-uri", help="s3://bucket/prefix/ of Parquet telemetry")
    parser.add_argument("--contamination", type=float, default=0.05)
    parser.add_argument("--output", default="anomalies_detected.csv")
    args = parser.parse_args()

    if args.s3_uri:
        df = load_s3_parquet(args.s3_uri)
    elif args.input:
        df = load_local_csv(args.input)
    else:
        parser.error("Provide either --input or --s3-uri")

    df = engineer_features(df)
    df = apply_rule_overlay(df)
    df = run_isolation_forest(df, contamination=args.contamination)

    df["is_anomaly"] = df["is_ml_anomaly"] | df["rule_continuous_overuse"] | df["rule_off_hours_activity"]
    flagged = df[df["is_anomaly"]]

    print(f"Scored {len(df)} readings, flagged {len(flagged)} anomalies.")
    flagged.to_csv(args.output, index=False)
    print(f"Saved flagged anomalies to {args.output}")


if __name__ == "__main__":
    main()
