"""OverdueCheckLambda.

Triggered nightly by an EventBridge cron rule (06:00 UTC). Scans all ACTIVE
rental contracts via the `status-index` GSI, computes each contract's
remaining days against its expected return date, and dispatches a CRITICAL
alert for anything overdue (remaining_days < 0) and a WARNING for anything
due within 2 days.
"""
import logging
import os
from datetime import date, datetime

import boto3

logger = logging.getLogger()
logger.setLevel(logging.INFO)

dynamodb = boto3.resource("dynamodb")
sns = boto3.client("sns")

CONTRACTS_TABLE = os.environ["CONTRACTS_TABLE"]
ALERT_TOPIC_ARN = os.environ["ALERT_TOPIC_ARN"]

DUE_SOON_DAYS = 2

contracts_table = dynamodb.Table(CONTRACTS_TABLE)


def _remaining_days(expected_return_date: str) -> int:
    expected = datetime.strptime(expected_return_date, "%Y-%m-%d").date()
    return (expected - date.today()).days


def _active_contracts():
    kwargs = {
        "IndexName": "status-index",
        "KeyConditionExpression": "#s = :active",
        "ExpressionAttributeNames": {"#s": "status"},
        "ExpressionAttributeValues": {":active": "ACTIVE"},
    }
    while True:
        resp = contracts_table.query(**kwargs)
        yield from resp.get("Items", [])
        last_key = resp.get("LastEvaluatedKey")
        if not last_key:
            break
        kwargs["ExclusiveStartKey"] = last_key


def _publish_overdue_alert(contract: dict, remaining_days: int) -> None:
    severity = "CRITICAL" if remaining_days < 0 else "WARNING"
    if remaining_days < 0:
        summary = f"OVERDUE by {abs(remaining_days)} day(s)"
    else:
        summary = f"due in {remaining_days} day(s)"

    message = (
        f"Contract {contract['contract_id']} for equipment "
        f"{contract.get('equipment_id')} at site {contract.get('site_id')} is {summary}. "
        f"Expected return date: {contract.get('expected_return_date')}."
    )
    sns.publish(
        TopicArn=ALERT_TOPIC_ARN,
        Subject=f"[CAT_RENTALS] {severity}: contract {contract['contract_id']}",
        Message=message,
        MessageAttributes={
            "contract_id": {"DataType": "String", "StringValue": contract["contract_id"]},
            "severity": {"DataType": "String", "StringValue": severity},
        },
    )


def handler(event, context):
    checked = 0
    alerted = 0

    for contract in _active_contracts():
        expected_return_date = contract.get("expected_return_date")
        if not expected_return_date:
            continue

        checked += 1
        remaining_days = _remaining_days(expected_return_date)

        contracts_table.update_item(
            Key={"contract_id": contract["contract_id"]},
            UpdateExpression="SET remaining_days = :r",
            ExpressionAttributeValues={":r": remaining_days},
        )

        if remaining_days <= DUE_SOON_DAYS:
            _publish_overdue_alert(contract, remaining_days)
            alerted += 1

    logger.info("Overdue check complete: checked=%d alerted=%d", checked, alerted)
    return {"checked": checked, "alerted": alerted}
