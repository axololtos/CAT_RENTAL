"""Seeds sample rows into RentalContracts and EquipmentLiveState for a smoke
test after `cdk deploy`.

Usage:
    AWS_REGION=us-east-1 python seed_dynamodb.py

    # Or against a local LocalStack instance (see ../local/):
    AWS_ENDPOINT_URL=http://localhost:4566 python seed_dynamodb.py
"""
import os
from datetime import date, timedelta
from decimal import Decimal

import boto3

region = os.getenv("AWS_REGION", "us-east-1")
endpoint_url = os.getenv("AWS_ENDPOINT_URL")  # set for LocalStack, unset for real AWS
dynamodb = boto3.resource("dynamodb", region_name=region, endpoint_url=endpoint_url)

contracts_table = dynamodb.Table(os.getenv("DYNAMODB_CONTRACTS_TABLE", "RentalContracts"))
state_table = dynamodb.Table(os.getenv("DYNAMODB_STATE_TABLE", "EquipmentLiveState"))

today = date.today()

sample_contracts = [
    {
        "contract_id": "C-1001",
        "equipment_id": "EQX1001",
        "site_id": "SITE-A",
        "status": "ACTIVE",
        "check_in_date": (today - timedelta(days=5)).isoformat(),
        "expected_return_date": (today + timedelta(days=3)).isoformat(),
        "operator_id": "OP-204",
    },
    {
        "contract_id": "C-1002",
        "equipment_id": "EQX1002",
        "site_id": "SITE-B",
        "status": "ACTIVE",
        "check_in_date": (today - timedelta(days=20)).isoformat(),
        "expected_return_date": (today - timedelta(days=1)).isoformat(),  # already overdue
        "operator_id": "OP-118",
    },
    {
        "contract_id": "C-1003",
        "equipment_id": "EQX1003",
        "site_id": "SITE-A",
        "status": "CLOSED",
        "check_in_date": (today - timedelta(days=60)).isoformat(),
        "expected_return_date": (today - timedelta(days=45)).isoformat(),
        "operator_id": "OP-057",
    },
]

sample_state = [
    {
        "equipment_id": "EQX1001",
        "site_id": "SITE-A",
        "last_seen": today.isoformat(),
        "engine_hours_today": Decimal("6.5"),
        "idle_hours_today": Decimal("1.0"),
        "operator_rfid": "RFID-204",
    },
    {
        "equipment_id": "EQX1002",
        "site_id": "SITE-B",
        "last_seen": today.isoformat(),
        "engine_hours_today": Decimal("2.0"),
        "idle_hours_today": Decimal("5.0"),
        "operator_rfid": "RFID-118",
    },
]


def main():
    with contracts_table.batch_writer() as batch:
        for item in sample_contracts:
            batch.put_item(Item=item)
    print(f"Seeded {len(sample_contracts)} rows into {contracts_table.table_name}")

    with state_table.batch_writer() as batch:
        for item in sample_state:
            batch.put_item(Item=item)
    print(f"Seeded {len(sample_state)} rows into {state_table.table_name}")


if __name__ == "__main__":
    main()
