"""AnomalyDetectionLambda.

Invoked directly by the AWS IoT Core topic rule on every message published to
`fleet/telemetry/v1`. Cross-references the live telemetry reading against the
equipment's active rental contract in DynamoDB and flags:

  - UNASSIGNED_USAGE     engine running but no active contract for the equipment
  - MISSING_OPERATOR_TAG engine running but no operator RFID tag was scanned
  - EXCESSIVE_IDLING     idle time exceeds 60% of total engine-on time today

Also upserts the equipment's row in EquipmentLiveState so the dashboard always
reflects the latest reading.
"""
import logging
import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

CONTRACTS_TABLE = os.environ["CONTRACTS_TABLE"]
STATE_TABLE = os.environ["STATE_TABLE"]
ALERT_TOPIC_ARN = os.environ["ALERT_TOPIC_ARN"]

IDLE_RATIO_THRESHOLD = 0.60

contracts_table = dynamodb.Table(CONTRACTS_TABLE)
state_table = dynamodb.Table(STATE_TABLE)


def _active_contract(equipment_id: str) -> dict | None:
    resp = contracts_table.query(
        IndexName="equipment-index",
        KeyConditionExpression="equipment_id = :eid AND #s = :active",
        ExpressionAttributeNames={"#s": "status"},
        ExpressionAttributeValues={":eid": equipment_id, ":active": "ACTIVE"},
        Limit=1,
    )
    items = resp.get("Items", [])
    return items[0] if items else None


def _detect_anomalies(reading: dict, contract: dict | None) -> list[str]:
    engine_hours = float(reading.get("engine_hours_today", 0) or 0)
    idle_hours = float(reading.get("idle_hours_today", 0) or 0)
    operator_rfid = reading.get("operator_rfid")

    anomalies = []
    if engine_hours > 0 and contract is None:
        anomalies.append("UNASSIGNED_USAGE")
    if engine_hours > 0 and not operator_rfid:
        anomalies.append("MISSING_OPERATOR_TAG")

    total_hours = engine_hours + idle_hours
    if total_hours > 0 and (idle_hours / total_hours) > IDLE_RATIO_THRESHOLD:
        anomalies.append("EXCESSIVE_IDLING")

    return anomalies


def _publish_alert(equipment_id: str, site_id: str, anomalies: list[str], reading: dict) -> None:
    message = (
        f"Anomaly detected for equipment {equipment_id} at site {site_id}: "
        f"{', '.join(anomalies)}. "
        f"engine_hours_today={reading.get('engine_hours_today')}, "
        f"idle_hours_today={reading.get('idle_hours_today')}, "
        f"operator_rfid={reading.get('operator_rfid') or 'MISSING'}"
    )
    sns.publish(
        TopicArn=ALERT_TOPIC_ARN,
        Subject=f"[CAT_RENTALS] Anomaly: {equipment_id}",
        Message=message,
        MessageAttributes={
            "equipment_id": {"DataType": "String", "StringValue": equipment_id},
            "severity": {"DataType": "String", "StringValue": "WARNING"},
        },
    )


def _decimal_or_none(value) -> Decimal | None:
    # DynamoDB's boto3 resource rejects native float; Decimal is required.
    return None if value is None else Decimal(str(value))


def handler(event, context):
    equipment_id = event.get("equipment_id")
    if not equipment_id:
        logger.warning("Telemetry message missing equipment_id: %s", event)
        return {"status": "ignored", "reason": "missing equipment_id"}

    site_id = event.get("site_id", "UNKNOWN")
    now_iso = datetime.now(timezone.utc).isoformat()

    contract = _active_contract(equipment_id)
    anomalies = _detect_anomalies(event, contract)

    state_table.put_item(
        Item={
            "equipment_id": equipment_id,
            "site_id": site_id,
            "last_seen": now_iso,
            "engine_hours_today": _decimal_or_none(event.get("engine_hours_today", 0)),
            "idle_hours_today": _decimal_or_none(event.get("idle_hours_today", 0)),
            "fuel_level_pct": _decimal_or_none(event.get("fuel_level_pct")),
            "operator_rfid": event.get("operator_rfid"),
            "lat": _decimal_or_none(event.get("lat")),
            "lon": _decimal_or_none(event.get("lon")),
            "contract_id": contract["contract_id"] if contract else None,
            "anomalies": anomalies,
        }
    )

    if anomalies:
        logger.info("Anomalies for %s: %s", equipment_id, anomalies)
        _publish_alert(equipment_id, site_id, anomalies, event)

    return {"status": "processed", "equipment_id": equipment_id, "anomalies": anomalies}
