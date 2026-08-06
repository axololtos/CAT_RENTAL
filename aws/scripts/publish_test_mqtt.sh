#!/usr/bin/env bash
# Publishes one test telemetry message to fleet/telemetry/v1 via AWS IoT Core,
# using the AWS CLI's iot-data plane API (no MQTT client required).
#
# Usage:
#   AWS_REGION=us-east-1 ./publish_test_mqtt.sh
set -euo pipefail

REGION="${AWS_REGION:-us-east-1}"
TOPIC="fleet/telemetry/v1"

# Resolve this account's IoT Core data-plane endpoint.
ENDPOINT=$(aws iot describe-endpoint --endpoint-type iot:Data-ATS --region "$REGION" --query endpointAddress --output text)

PAYLOAD=$(cat <<'EOF'
{
  "equipment_id": "EQX1001",
  "site_id": "SITE-A",
  "timestamp": "2026-08-05T09:00:00Z",
  "engine_hours_today": 7.2,
  "idle_hours_today": 1.1,
  "fuel_level_pct": 62.5,
  "operator_rfid": "RFID-204",
  "lat": 37.7749,
  "lon": -122.4194,
  "status": "RUNNING"
}
EOF
)

echo "Publishing to $TOPIC via $ENDPOINT ..."
aws iot-data publish \
  --endpoint-url "https://${ENDPOINT}" \
  --topic "$TOPIC" \
  --region "$REGION" \
  --cli-binary-format raw-in-base64-out \
  --payload "$PAYLOAD"

echo "Done. Check CloudWatch Logs for AnomalyDetectionLambda and the S3 data lake for the Firehose-delivered Parquet object."
