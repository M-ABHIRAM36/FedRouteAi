# How to Run FedRouteAI

Run the commands below from the repository root:

```text
C:\Users\DELL\Desktop\Major Project\fedrouteai
```

## Prerequisites

- Python 3.12 or newer
- Node.js 18 or newer, including `npm`
- PostgreSQL with PostGIS for database-backed API data

Install Python and frontend dependencies once:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt
Set-Location frontend
npm install
Set-Location ..
```

The repository already contains `backend\.env`. Confirm its PostgreSQL values
match the local database before using database-backed pages.

## Start Frontend and Backend Together

The root launcher starts FastAPI and Vite and stops both when Ctrl+C is pressed:

```powershell
python run_project.py
```

Open:

- Dashboard: http://127.0.0.1:5173
- Backend: http://127.0.0.1:8000
- Swagger API documentation: http://127.0.0.1:8000/docs

The backend starts without PostgreSQL, but database-backed endpoints will be
empty or unavailable until PostgreSQL is running and the database is seeded.

## Include the Live Simulator

Start frontend, backend, and the standalone live simulator together:

```powershell
python run_project.py --with-simulator
```

The simulator prints one summary for each generated tick. It uses the canonical
130-segment, 8-region V1 network and generates 1,000 persistent vehicle
observations per tick by default. This mode remains isolated and does not need
backend or database connectivity.

## Persist Live Simulator Traffic

Apply the live-ingestion migration once, then start the backend and simulator
with the same ingestion API key:

```powershell
Set-Location backend
$env:PYTHONPATH = "."
..\.venv\Scripts\python.exe -m alembic upgrade head
Set-Location ..
$env:LIVE_INGEST_API_KEY = "replace-with-a-local-secret"
python run_project.py --backend-only --with-ingestion --simulator-ticks 10
```

`--with-ingestion` sends each pre-matched multi-vehicle tick to
`POST /api/v1/ingest/live/batch`. Historical observations are appended to
`gps_pings`, while the latest per-segment projection is upserted into
`segment_current_state`. Batch retries are idempotent by
`(source_id, run_id, batch_id)` and require `X-Live-Ingest-Key`.

Use `--ingest-api-key <value>` instead of the environment variable when useful.
The backend readiness check waits up to 30 seconds before the simulator starts.

## Component-Only Commands

Backend only:

```powershell
python run_project.py --backend-only
```

Frontend only:

```powershell
python run_project.py --frontend-only
```

Simulator only, continuously:

```powershell
python run_project.py --simulator-only
```

Simulator only for 10 ticks:

```powershell
python run_project.py --simulator-only --simulator-ticks 10
```

Custom simulator configuration:

```powershell
python run_project.py --simulator-only --pings-per-tick 500 --tick-seconds 2 --seed 7
```

Custom server ports:

```powershell
python run_project.py --backend-port 8010 --frontend-port 5180
```

The current frontend API URLs are configured for backend port `8000`. Use the
default backend port for normal frontend operation.

## Manual Startup

Use separate terminals when process output needs to remain separated.

Terminal 1, backend:

```powershell
Set-Location backend
$env:PYTHONPATH = "."
..\.venv\Scripts\python.exe -m uvicorn app.main:app --reload
```

Terminal 2, frontend:

```powershell
Set-Location frontend
npm run dev
```

Terminal 3, optional simulator:

```powershell
python run_project.py --simulator-only
```

## Database Setup

Start an existing PostgreSQL/PostGIS installation, or use the container command
documented in `README.md`. Generate and seed the V1 dataset only when the local
database has not already been seeded:

```powershell
bash scripts/generate_dataset_then_seed.sh
```

This script requires a Bash environment such as Git Bash or WSL. Do not rerun it
merely to start the application because dataset generation is separate from
normal application startup.

## Tests

Run the complete backend suite:

```powershell
Set-Location backend
$env:PYTHONPATH = "."
..\.venv\Scripts\python.exe -m pytest tests -v
```

Run only live simulator validation:

```powershell
Set-Location backend
$env:PYTHONPATH = "."
..\.venv\Scripts\python.exe -m pytest tests\test_live_simulation.py -v
```

Run live-ingestion validation:

```powershell
Set-Location backend
$env:PYTHONPATH = "."
..\.venv\Scripts\python.exe -m pytest tests\test_live_ingestion.py -v
```

## Ingestion Diagnostics

Run an end-to-end benchmark against an already running backend:

```powershell
.\.venv\Scripts\python.exe scripts\verify_live_ingestion.py `
  --ticks 10 --pings 1000 --run-id manual-check-001 `
  --url http://127.0.0.1:8000 --api-key replace-with-a-local-secret
```

Useful PostgreSQL checks:

```sql
SELECT count(*), min(timestamp), max(timestamp),
       count(DISTINCT region_id), count(DISTINCT segment_id),
       count(DISTINCT vehicle_id)
FROM gps_pings
WHERE ingestion_batch_id IS NOT NULL;

SELECT source_id, run_id, count(*) AS batches, sum(accepted_count) AS rows
FROM live_ingestion_batches
GROUP BY source_id, run_id
ORDER BY max(received_at) DESC;

SELECT segment_id, region_id, latest_timestamp, vehicle_count,
       average_speed_kmph, current_event, available
FROM segment_current_state
ORDER BY segment_id;
```
