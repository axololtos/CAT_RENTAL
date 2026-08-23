"""Creates the DynamoDB tables, S3 bucket, and SNS topic used by the
dashboard-integration demo, directly against LocalStack.

This intentionally does not go through CDK: the CDK stack in ../cdk also
provisions IoT Core, Kinesis Firehose, and Glue, none of which LocalStack's
free edition supports. Rather than have `cdk deploy` fail partway through,
this script creates just the LocalStack-supported subset with plain boto3,
matching the same table/key/GSI shapes as cat_rentals_stack.py.

Usage:
    docker compose -f docker-compose.yml up -d
    python bootstrap_localstack.py
"""
import boto3
from botocore.exceptions import ClientError

ENDPOINT_URL = "http://localhost:4566"
REGION = "us-east-1"
# LocalStack ignores credentials, but boto3 requires something be set.
CREDENTIALS = {"aws_access_key_id": "test", "aws_secret_access_key": "test"}

CONTRACTS_TABLE = "RentalContracts"
STATE_TABLE = "EquipmentLiveState"
BUCKET_NAME = "cat-rentals-telemetry-lake-local"
TOPIC_NAME = "cat-rentals-alerts"


def _client(service: str):
    return boto3.client(service, endpoint_url=ENDPOINT_URL, region_name=REGION, **CREDENTIALS)


def _table_exists(dynamodb, table_name: str) -> bool:
    try:
        dynamodb.describe_table(TableName=table_name)
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] == "ResourceNotFoundException":
            return False
        raise


def create_contracts_table(dynamodb):
    if _table_exists(dynamodb, CONTRACTS_TABLE):
        print(f"{CONTRACTS_TABLE} already exists, skipping")
        return

    dynamodb.create_table(
        TableName=CONTRACTS_TABLE,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "contract_id", "AttributeType": "S"},
            {"AttributeName": "equipment_id", "AttributeType": "S"},
            {"AttributeName": "status", "AttributeType": "S"},
            {"AttributeName": "expected_return_date", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "contract_id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "equipment-index",
                "KeySchema": [
                    {"AttributeName": "equipment_id", "KeyType": "HASH"},
                    {"AttributeName": "status", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
            {
                "IndexName": "status-index",
                "KeySchema": [
                    {"AttributeName": "status", "KeyType": "HASH"},
                    {"AttributeName": "expected_return_date", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            },
        ],
    )
    print(f"Created {CONTRACTS_TABLE}")


def create_state_table(dynamodb):
    if _table_exists(dynamodb, STATE_TABLE):
        print(f"{STATE_TABLE} already exists, skipping")
        return

    dynamodb.create_table(
        TableName=STATE_TABLE,
        BillingMode="PAY_PER_REQUEST",
        AttributeDefinitions=[
            {"AttributeName": "equipment_id", "AttributeType": "S"},
            {"AttributeName": "site_id", "AttributeType": "S"},
            {"AttributeName": "last_seen", "AttributeType": "S"},
        ],
        KeySchema=[{"AttributeName": "equipment_id", "KeyType": "HASH"}],
        GlobalSecondaryIndexes=[
            {
                "IndexName": "site-index",
                "KeySchema": [
                    {"AttributeName": "site_id", "KeyType": "HASH"},
                    {"AttributeName": "last_seen", "KeyType": "RANGE"},
                ],
                "Projection": {"ProjectionType": "ALL"},
            }
        ],
    )
    print(f"Created {STATE_TABLE}")


def create_bucket(s3):
    if BUCKET_NAME in [b["Name"] for b in s3.list_buckets().get("Buckets", [])]:
        print(f"{BUCKET_NAME} already exists, skipping")
        return
    s3.create_bucket(Bucket=BUCKET_NAME)
    print(f"Created bucket {BUCKET_NAME}")


def create_topic(sns) -> str:
    topic_arn = sns.create_topic(Name=TOPIC_NAME)["TopicArn"]
    print(f"Topic ready: {topic_arn}")
    return topic_arn


def main():
    dynamodb = _client("dynamodb")
    s3 = _client("s3")
    sns = _client("sns")

    create_contracts_table(dynamodb)
    create_state_table(dynamodb)
    create_bucket(s3)
    topic_arn = create_topic(sns)

    print("\nLocalStack is ready. Point the backend at it with:")
    print("  USE_DYNAMODB=true")
    print(f"  DYNAMODB_ENDPOINT_URL={ENDPOINT_URL}")
    print(f"  SNS_ALERT_TOPIC_ARN={topic_arn}")


if __name__ == "__main__":
    main()
