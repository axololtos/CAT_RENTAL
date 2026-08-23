"""Application settings — configurable via environment variables."""

from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Smart Rental Tracking System"
    debug: bool = False

    # Data source
    data_source_type: str = "local"  # local | cloud
    cloud_csv_url: str = ""
    local_csv_path: str = "data/equipment_rentals.csv"
    refresh_interval_seconds: int = 30

    # Database for transactions
    sqlite_path: str = "data/rentals.db"

    # Utilization thresholds (%)
    util_low_max: float = 30.0
    util_moderate_max: float = 60.0
    util_good_max: float = 80.0

    # Anomaly thresholds
    idle_hours_anomaly_threshold: float = 8.0
    long_rental_days_threshold: int = 45
    high_engine_hours_threshold: float = 10.0
    low_utilization_anomaly_threshold: float = 20.0

    # Alert thresholds (days)
    due_soon_days: int = 3
    due_tomorrow_days: int = 1

    # Forecast
    forecast_horizon_days: int = 30
    min_forecast_records: int = 20
    use_demo_forecast_data: bool = False

    # Optional DynamoDB mirror (see aws/local/ for a LocalStack demo, or
    # aws/cdk/ for the real-AWS stack). Off by default — the app runs fully
    # standalone on local CSV/SQLite without this.
    use_dynamodb: bool = False
    aws_region: str = "us-east-1"
    dynamodb_endpoint_url: str = ""  # e.g. http://localhost:4566 for LocalStack; empty = real AWS
    dynamodb_contracts_table: str = "RentalContracts"
    dynamodb_state_table: str = "EquipmentLiveState"


@lru_cache
def get_settings() -> Settings:
    return Settings()
