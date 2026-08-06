# Smart Rental Tracking System

Production-quality prototype for Caterpillar industrial equipment rental tracking.

## Terminology (critical)

| Term | Meaning |
|------|---------|
| **Check-In** | Equipment **leaves** the company (rented out) |
| **Check-Out** | Equipment **returns** to the company |

Example: EQX1001 Check-In `2025-04-01`, Check-Out `2025-04-16` means it left on April 1 and returned on April 16.

## Problem statement

Construction and mining companies rent heavy machinery through dealers. Spreadsheet-based tracking causes lost equipment, misallocation, unexpected extensions, high idle time, and poor demand visibility.

This system provides:

1. **Asset Dashboard** — live status for all equipment  
2. **Check-In / Check-Out** — manual entry + QR-ready flow  
3. **Usage Logging** — runtime, idle, site, operator analytics  
4. **Summaries** — rented hours, site usage, downtime  
5. **Overdue alerts & notifications** — based on Expected Return Date  
6. **Demand Forecasting** — equipment type × site predictions  
7. **Anomaly Detection** — rule-based + Isolation Forest ML  

## Architecture

```
Cloud CSV / Local CSV / (future: DB · API · IoT)
        ↓
Data ingestion + validation
        ↓
Application backend (FastAPI)
        ↓
Analytics · Alert · ML / Forecast · Recommendation engines
        ↓
React dashboard (Vite + Tailwind + Recharts)
```

All KPI values, charts, alerts, and predictions are derived from loaded data — never hardcoded.

## Tech stack

- **Frontend:** React 19, TypeScript, Vite, Tailwind CSS v4, Recharts, React Router, qrcode.react  
- **Backend:** Python FastAPI, Pydantic, pandas, scikit-learn, SQLite  
- **ML:** Isolation Forest (anomalies); Moving Average / Random Forest / Gradient Boosting (forecast)

## Folder structure

```
caterpillar/
├── backend/
│   ├── api/routes.py
│   ├── services/          # ingestion, alerts, analytics, rentals, engine
│   ├── ml/                # anomaly_detector, forecasting
│   ├── models/schemas.py
│   ├── utils/             # config, status
│   ├── data/equipment_rentals.csv
│   ├── tests/
│   └── main.py
├── frontend/
│   └── src/
│       ├── components/
│       ├── pages/
│       ├── services/
│       ├── hooks/
│       ├── layouts/
│       └── types/
└── README.md
```

## Installation

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Frontend

```bash
cd frontend
npm install
```

## Running

### Backend (port 8000)

```bash
cd backend
source .venv/bin/activate
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

OpenAPI docs: http://127.0.0.1:8000/docs

### Frontend (port 5173)

```bash
cd frontend
npm run dev
```

App: http://127.0.0.1:5173  
Vite proxies `/api` → backend.

## Environment variables

Configured in `backend/.env`:

| Variable | Description | Default |
|----------|-------------|---------|
| `DATA_SOURCE_TYPE` | `local` or `cloud` | `local` |
| `CLOUD_CSV_URL` | URL to cloud-hosted CSV | empty |
| `LOCAL_CSV_PATH` | Path relative to backend/ | `data/equipment_rentals.csv` |
| `REFRESH_INTERVAL_SECONDS` | Polling interval | `30` |
| `SQLITE_PATH` | Transaction DB | `data/rentals.db` |
| `USE_DYNAMODB` | Mirror Check-In/Check-Out into DynamoDB (real AWS or local) | `false` |
| `DYNAMODB_ENDPOINT_URL` | Set to `http://localhost:4566` for the local demo; empty for real AWS | empty |
| `DYNAMODB_CONTRACTS_TABLE` / `DYNAMODB_STATE_TABLE` | Table names | `RentalContracts` / `EquipmentLiveState` |

Thresholds (utilization, idle anomaly, due-soon, forecast) are also adjustable via **Settings** in the UI.

`USE_DYNAMODB` is off by default and everything above still works exactly as described with it off. See `aws/local/README.md` for a zero-cost, no-AWS-account walkthrough that wires this toggle up to LocalStack in Docker.

## Local CSV

Place or edit:

```
backend/data/equipment_rentals.csv
```

Required columns (compatible with the official sample):

`Equipment ID, Type, Site ID, Check-In Date, Check-Out Date, Engine Hours/Day, Idle Hours/Day, Rental Days, Last Operator ID`

Optional: `Expected Return Date` (required for overdue logic on active rentals).

Active rentals: Check-In set, Check-Out empty/NULL.

## Cloud CSV

1. Host a CSV at a public HTTPS URL (or reachable URL).  
2. Set `DATA_SOURCE_TYPE=cloud` and `CLOUD_CSV_URL=…` in `.env`, **or** use Settings in the UI.  
3. Click **Refresh Data** or wait for polling.

## Real-time refresh

- Frontend polls every N seconds (default 30) without full page reload.  
- Top bar shows **Last updated** and **Data Source Status**.  
- **Refresh Data** triggers `POST /api/refresh`.  
- Malformed rows are skipped with warnings — the app does not crash.

## Anomaly detection

**Rule-based:** high idle, zero engine + high idle, missing site/operator, activity without assignment, long rentals, high engine hours, very low utilization.

**ML:** Isolation Forest on engine/idle/rental days/utilization/type/site-presence. Results labeled **Potential anomaly**.

## Demand forecasting

1. Aggregates historical Check-Ins by week × site × type.  
2. Time-aware train/test split (no random shuffle).  
3. Compares Moving Average, Random Forest, Gradient Boosting; picks lowest MAE.  
4. Forecasts next 7 / 30 days.  
5. If data is insufficient: shows a clear message. Optional **Demo Mode** uses generated history only (never mixed with production rows).

## API endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/health` | Health + data source |
| POST | `/api/refresh` | Reload CSV |
| GET | `/api/dashboard` | KPIs + charts payload |
| GET | `/api/equipment` | List / filter |
| GET | `/api/equipment/{id}` | Detail |
| GET | `/api/analytics` | Usage analytics |
| GET | `/api/alerts` | Alerts |
| GET | `/api/anomalies` | Anomaly summary |
| GET | `/api/forecast` | Demand forecast |
| GET | `/api/recommendations` | Smart recommendations |
| GET | `/api/rentals` | Rental history |
| POST | `/api/check-in` | Rent out |
| POST | `/api/check-out` | Return |
| GET/PUT | `/api/settings` | Configuration |
| GET | `/api/reports/export` | CSV export |
| GET | `/api/notifications` | Notification center |

## Tests

```bash
cd backend
source .venv/bin/activate
pytest -v
```

Critical coverage: Check-In/Out terminology, utilization (incl. zero), overdue/due-soon, missing values, anomaly rules, invalid dates, duplicates.

## Screenshots

Add screenshots of Dashboard, Assets, Anomalies, Forecast, and Check-In/Out here after demo.

## Assumptions

- Sample CSV includes official problem-statement rows plus additional historical and active rentals for a richer demo.  
- Overdue logic uses **Expected Return Date**, never historical Check-Out.  
- Fuel usage is not in the CSV; runtime/idle hours are used as the usage signal.  
- Transaction overrides (Check-In/Out) are stored in SQLite and layered over CSV data.

## Cloud / AWS deployment

An optional AWS-native telemetry & alerting layer (DynamoDB, IoT Core,
Kinesis Firehose, Lambda, SNS, Greengrass edge buffering, XGBoost/Isolation
Forest training scripts) lives in `aws/`. See `aws/README.md` for credential
setup and deployment steps. It's additive — the local prototype above runs
independently of it.

## Future improvements

- Persistent equipment master DB + IoT telematics connectors  
- RFID hardware integration  
- Role-based auth (dealer / site / admin)  
- PDF report generation  
- Online learning for anomaly models with labeled feedback  

## License

Prototype for interview / evaluation use.
