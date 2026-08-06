"""Best-effort mirror of Check-In/Check-Out activity into DynamoDB.

Disabled by default (`USE_DYNAMODB=false`) — the app's local CSV/SQLite
behavior is unchanged either way. When enabled, it points at either a real
AWS account or a local LocalStack instance (see aws/local/) via
`DYNAMODB_ENDPOINT_URL`, and mirrors the same RentalContracts /
EquipmentLiveState shape that aws/cdk/cat_rentals_stack.py provisions, so
the AnomalyDetectionLambda / OverdueCheckLambda logic can be exercised
against real dashboard actions.

Failures here (e.g. LocalStack not running) are logged and swallowed —
mirroring is a demo/observability aid, never a reason to fail a Check-In or
Check-Out request.
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache
from typing import Optional

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from models.schemas import EquipmentRecord
from utils.config import get_settings

logger = logging.getLogger(__name__)


@lru_cache
def _resource():
    settings = get_settings()
    return boto3.resource(
        "dynamodb",
        region_name=settings.aws_region,
        endpoint_url=settings.dynamodb_endpoint_url or None,
    )


def _contracts_table():
    return _resource().Table(get_settings().dynamodb_contracts_table)


def _state_table():
    return _resource().Table(get_settings().dynamodb_state_table)


def _contract_id(equipment_id: str, check_in_date) -> str:
    return f"{equipment_id}#{check_in_date.isoformat()}"


def _mirror_live_state(record: EquipmentRecord) -> None:
    _state_table().put_item(
        Item={
            "equipment_id": record.equipment_id,
            "site_id": record.site_id or "UNKNOWN",
            "last_seen": datetime.now(timezone.utc).isoformat(),
            # DynamoDB's boto3 resource rejects native float; Decimal is required.
            "engine_hours_today": Decimal(str(record.engine_hours_per_day or 0)),
            "idle_hours_today": Decimal(str(record.idle_hours_per_day or 0)),
            "operator_rfid": record.last_operator_id,
        }
    )


def mirror_check_in(record: EquipmentRecord) -> None:
    """Best-effort: create/refresh the ACTIVE contract row for this equipment."""
    if not get_settings().use_dynamodb:
        return
    if not record.check_in_date:
        return

    try:
        _contracts_table().put_item(
            Item={
                "contract_id": _contract_id(record.equipment_id, record.check_in_date),
                "equipment_id": record.equipment_id,
                "site_id": record.site_id or "UNKNOWN",
                "status": "ACTIVE",
                "check_in_date": record.check_in_date.isoformat(),
                "expected_return_date": (
                    record.expected_return_date.isoformat() if record.expected_return_date else None
                ),
                "operator_id": record.last_operator_id,
            }
        )
        _mirror_live_state(record)
    except (ClientError, BotoCoreError) as exc:
        logger.warning("DynamoDB mirror (check-in) skipped: %s", exc)


def mirror_check_out(equipment_id: str, record: EquipmentRecord) -> None:
    """Best-effort: close the ACTIVE contract for this equipment, if one exists."""
    if not get_settings().use_dynamodb:
        return

    try:
        active = _find_active_contract(equipment_id)
        if active is None:
            logger.warning("No ACTIVE DynamoDB contract found to close for %s", equipment_id)
            return

        _contracts_table().update_item(
            Key={"contract_id": active["contract_id"]},
            UpdateExpression="SET #s = :closed, check_out_date = :co",
            ExpressionAttributeNames={"#s": "status"},
            ExpressionAttributeValues={
                ":closed": "CLOSED",
                ":co": record.check_out_date.isoformat() if record.check_out_date else None,
            },
        )
        _mirror_live_state(record)
    except (ClientError, BotoCoreError) as exc:
        logger.warning("DynamoDB mirror (check-out) skipped: %s", exc)


def _find_active_contract(equipment_id: str) -> Optional[dict]:
    resp = _contracts_table().query(
        IndexName="equipment-index",
        KeyConditionExpression="equipment_id = :eid AND #s = :active",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":eid": equipment_id, ":active": "ACTIVE"},
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None
