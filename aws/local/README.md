# Local demo: dashboard → DynamoDB (no AWS account needed)

Runs the same DynamoDB tables the real stack uses, but emulated locally by
[LocalStack](https://www.localstack.io/) in Docker — no AWS account, no
credentials, no cost, nothing to tear down. This wires the **existing
dashboard's Check-In / Check-Out form** so that submitting it also writes a
row into a local `RentalContracts` / `EquipmentLiveState` table, which you
can inspect directly.

**Scope:** this covers the "dashboard → DynamoDB → Lambda alerting" half of
the architecture. LocalStack's free edition doesn't support IoT Core,
Kinesis Firehose, or Glue, so the device-telemetry ingestion path (edge
gateway → IoT Core → Firehose → S3 Parquet lake) isn't part of this local
demo — see `../README.md` for that half, which needs real AWS.

## 1. Start LocalStack

```bash
cd aws/local
docker compose up -d
```

## 2. Create the tables/bucket/topic

```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python bootstrap_localstack.py
```

This creates `RentalContracts` and `EquipmentLiveState` with the same keys
and GSIs as `../cdk/cat_rentals_stack.py`, plus the S3 bucket and SNS topic,
directly against LocalStack (not through CDK — LocalStack's free tier can't
run the IoT/Firehose/Glue parts of the CDK stack anyway, so this uses plain
boto3 for just the supported subset).

## 3. Point the backend at it

```bash
cd ../../backend
source .venv/bin/activate   # create it first if you haven't: python3 -m venv .venv && pip install -r requirements.txt
USE_DYNAMODB=true DYNAMODB_ENDPOINT_URL=http://localhost:4566 \
  uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

(Or add `USE_DYNAMODB=true` / `DYNAMODB_ENDPOINT_URL=http://localhost:4566`
to `backend/.env` instead of passing them inline.)

## 4. Use the dashboard normally

```bash
cd ../frontend
npm run dev
```

Open the app, go to **Check-In / Check-Out**, and submit a Check-In for any
equipment ID. The SQLite-backed dashboard behaves exactly as before — this
is additive, not a replacement — but the same submission now also lands in
the local DynamoDB table.

## 5. Verify it landed

```bash
aws dynamodb scan --table-name RentalContracts --endpoint-url http://localhost:4566
aws dynamodb scan --table-name EquipmentLiveState --endpoint-url http://localhost:4566
```

Check equipment back out through the dashboard and re-run the scan — the
contract's `status` flips from `ACTIVE` to `CLOSED` with a `check_out_date`.

## How the mirror works

`backend/services/dynamo_repo.py` is called from `perform_check_in` /
`perform_check_out` in `backend/services/rentals.py`. It's a no-op unless
`USE_DYNAMODB=true`, and any AWS/LocalStack error is logged and swallowed —
a Check-In/Check-Out request never fails because the mirror couldn't reach
DynamoDB. `contract_id` is `{equipment_id}#{check_in_date}`; Check-Out finds
the equipment's `ACTIVE` contract via the `equipment-index` GSI and closes
it, same lookup pattern `AnomalyDetectionLambda` uses in the real stack.

## Shut down

```bash
docker compose down -v   # -v also drops the local table/bucket data
```

Nothing here creates any real AWS resource or requires any AWS credentials.
