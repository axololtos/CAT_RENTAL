# CAT_RENTALS — AWS Cloud Deployment

This directory adds an optional AWS-native telemetry & alerting layer on top
of the existing local prototype in `backend/` and `frontend/`. It is
additive: nothing here changes how the FastAPI/React app runs locally.

**Want to try this without an AWS account first?** See
[`local/README.md`](local/README.md) — runs the DynamoDB half of this stack
in Docker via LocalStack, wired to the existing dashboard's Check-In/
Check-Out form, at zero cost and with no credentials.

```
aws/
├── local/                       # LocalStack demo — no AWS account needed
│   ├── docker-compose.yml
│   ├── bootstrap_localstack.py
│   └── README.md
├── cdk/                        # AWS CDK (Python) — infrastructure as code
│   ├── app.py
│   ├── cat_rentals_stack.py
│   ├── cdk.json
│   ├── requirements.txt
│   └── lambda/
│       ├── anomaly_detection/anomaly_detection.py
│       └── overdue_check/overdue_check.py
├── ml/                          # Offline training scripts
│   ├── demand_forecast.py       # XGBoost 14-day demand forecast
│   ├── isolation_forest_anomaly.py
│   └── requirements.txt
├── edge/greengrass/             # AWS IoT Greengrass v2 edge gateway config
│   ├── recipe.json
│   ├── edge_buffer.py
│   └── requirements.txt
├── scripts/
│   ├── seed_dynamodb.py
│   └── publish_test_mqtt.sh
└── .env.example
```

## Architecture

```
Cat machine sensors / telematics
        │  (MQTT)
        ▼
Edge gateway (Greengrass v2 + Stream Manager + local SQLite buffer)
        │  publishes to fleet/telemetry/v1 (store-and-forward if offline)
        ▼
AWS IoT Core topic rule (fleet/telemetry/v1)
        │                              │
        ▼                              ▼
Kinesis Data Firehose            AnomalyDetectionLambda
  (JSON → Parquet)                 │  reads/writes DynamoDB
        │                          │  publishes SNS on anomaly
        ▼                          ▼
S3 data lake                  EquipmentLiveState (DynamoDB)
(cat-rentals-telemetry-lake)        │
        │                          ▼
        │                   RentalContracts (DynamoDB) ←── OverdueCheckLambda
        │                                                    (nightly, EventBridge)
        ▼
XGBoost demand forecast / Isolation Forest anomaly jobs (offline, ml/)
```

---

## Step 1 — AWS credentials & environment setup

**You run these steps yourself** — an AI coding session cannot create IAM
users or hold live AWS credentials for your account.

### 1.1 Create an IAM user and access keys

1. Sign in to the [AWS Console](https://console.aws.amazon.com/) as your root
   or an existing admin user.
2. Go to **IAM → Users → Create user**.
   - Name it e.g. `cat-rentals-deployer`.
   - Do **not** enable console access unless you need it.
3. Attach permissions: for a first deployment, attach the AWS-managed policy
   **AdministratorAccess** (tighten to a scoped policy — DynamoDB, S3, IoT,
   Kinesis Firehose, Lambda, SNS, EventBridge, Glue, CloudFormation, IAM
   PassRole — once the stack is stable).
4. Go to the user → **Security credentials → Access keys → Create access
   key** → choose "Command Line Interface (CLI)".
5. Copy the **Access Key ID** and **Secret Access Key** immediately — the
   secret is shown only once.

### 1.2 Configure the AWS CLI locally

```bash
aws configure
# AWS Access Key ID [None]: AKIA...
# AWS Secret Access Key [None]: ...
# Default region name [None]: us-east-1
# Default output format [None]: json
```

Verify:

```bash
aws sts get-caller-identity
```

### 1.3 Environment variables

Copy `aws/.env.example` to `aws/.env` and fill in real values (this file is
git-ignored — never commit it):

```bash
cp aws/.env.example aws/.env
```

```dotenv
AWS_REGION=us-east-1
AWS_ACCOUNT_ID=123456789012
DYNAMODB_CONTRACTS_TABLE=RentalContracts
DYNAMODB_STATE_TABLE=EquipmentLiveState
SNS_ALERT_TOPIC_ARN=arn:aws:sns:us-east-1:123456789012:cat-rentals-alerts
GITHUB_REPO_URL=https://github.com/axololtos/CAT_RENTAL.git
ALERT_EMAIL=
ANTHROPIC_API_KEY=
OPENAI_API_KEY=
```

`SNS_ALERT_TOPIC_ARN` isn't known until after the first `cdk deploy` —
either leave it blank until then, or fill it in from the CDK deploy output.
`ANTHROPIC_API_KEY` / `OPENAI_API_KEY` are only needed if you wire an AI
assistant feature into the frontend; generate one from your own Anthropic or
OpenAI account — never share or paste a real key into a chat session.

---

## Step 2 — What gets provisioned

See `cdk/cat_rentals_stack.py` for the full definition. Summary:

| Resource | Purpose |
|---|---|
| `RentalContracts` (DynamoDB) | PK `contract_id`; GSIs `equipment-index` (active contract lookup) and `status-index` (nightly overdue scan) |
| `EquipmentLiveState` (DynamoDB) | PK `equipment_id`; GSI `site-index` for fleet-by-site views |
| S3 bucket `cat-rentals-telemetry-lake-<account>-<region>` | Parquet telemetry lake with IA (30d) / Glacier (180d) lifecycle tiering |
| IoT topic rule `fleet/telemetry/v1` | Fans out to Firehose and `AnomalyDetectionLambda` |
| Kinesis Data Firehose | Buffers + converts JSON → Parquet (via Glue schema) → S3 |
| `AnomalyDetectionLambda` | Live: unassigned usage, missing operator RFID, >60% idle ratio |
| `OverdueCheckLambda` | Nightly (06:00 UTC, EventBridge): remaining-days + overdue/due-soon alerts |
| SNS topic `cat-rentals-alerts` | Delivers WARNING/CRITICAL alerts (email opt-in via `ALERT_EMAIL`) |
| IAM roles | One per Lambda/Firehose/IoT rule, scoped via CDK `grant_*` (least privilege, no wildcard resources) |

Bucket names must be globally unique, so the stack suffixes the requested
`cat-rentals-telemetry-lake` name with your account ID and region.

---

## Step 3 — Deploy

```bash
# 1. Clone and set up
git clone https://github.com/axololtos/CAT_RENTAL.git
cd CAT_RENTAL/aws/cdk
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 2. Bootstrap (one-time per account/region) and deploy
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=123456789012   # your account, from `aws sts get-caller-identity`
cdk bootstrap aws://$AWS_ACCOUNT_ID/$AWS_REGION
cdk deploy
```

`cdk deploy` prints a confirmation of IAM changes before creating anything —
review it, then approve. Note the `AlertTopic` ARN from the outputs and save
it into `aws/.env` as `SNS_ALERT_TOPIC_ARN`.

### Seed sample data

```bash
cd ../scripts
python3 -m venv .venv && source .venv/bin/activate
pip install boto3
AWS_REGION=us-east-1 python seed_dynamodb.py
```

### Publish a test MQTT message

```bash
AWS_REGION=us-east-1 ./publish_test_mqtt.sh
```

Then check:
- CloudWatch Logs → `/aws/lambda/AnomalyDetectionLambda` for the processed reading.
- The `EquipmentLiveState` table for the upserted row.
- The S3 bucket (`telemetry/` prefix) a few minutes later for the Parquet object (Firehose buffers up to 5 minutes / 128MB before flushing).

### Train the ML models (offline, run locally — not part of `cdk deploy`)

```bash
cd ../ml
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

python demand_forecast.py --input ../../backend/data/equipment_rentals.csv
python isolation_forest_anomaly.py --input ../../backend/data/equipment_rentals.csv
```

Swap `--input <csv>` for `--s3-uri s3://cat-rentals-telemetry-lake-<account>-<region>/telemetry/`
once the data lake has accumulated real telemetry.

### Tear down

```bash
cd ../cdk
cdk destroy
```

DynamoDB tables and the S3 bucket are set to `RETAIN` in the stack, so they
survive `cdk destroy` — delete them manually if you want a full teardown.

---

## Step 4 — Commit and push

```bash
git add aws/
git commit -m "Add AWS CDK infrastructure, Lambdas, ML scripts, and edge gateway config"
git push -u origin <your-branch>
```

---

## Edge gateway (Greengrass v2)

`edge/greengrass/recipe.json` defines `com.catrentals.EdgeTelemetryBuffer`, a
custom component that:

1. Writes every telemetry reading to a local SQLite table immediately
   (`edge_buffer.py`), so a reading is never lost even if the network is down.
2. Runs a background flush loop that forwards unsent rows to a Stream
   Manager stream (`CatRentalsTelemetryStream`), which exports onward to AWS
   IoT Core / Kinesis.
3. Backs off exponentially (up to 5 minutes) while the uplink is down, and
   resumes normal-speed flushing the moment Stream Manager reports success —
   this is the store-and-forward behavior for cellular outages.

To deploy it: upload `edge_buffer.py` and `requirements.txt` to an S3 bucket,
update the `Artifacts` URIs in `recipe.json` to point at that bucket, then
create the component version with the Greengrass v2 console or
`aws greengrassv2 create-component-version --inline-recipe fileb://recipe.json`.
