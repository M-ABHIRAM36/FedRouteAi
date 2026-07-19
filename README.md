# 🚦 FedRouteAI

Adaptive Federated Learning for Real-Time Route Detection

![Python](https://img.shields.io/badge/Python-3.10-blue)
![PyTorch](https://img.shields.io/badge/PyTorch-2.x-red)
![Flower](https://img.shields.io/badge/Flower-Federated%20Learning-orange)
![License](https://img.shields.io/badge/License-MIT-green)
![Status](https://img.shields.io/badge/Status-Stable-success)
![Release](https://img.shields.io/badge/Release-v1.0-blue)

Real-time road-event detection via privacy-preserving federated learning
and road-graph reasoning. See `docs/architecture.md` for the full design
rationale — this file is quickstart + orientation.

## What's actually in this repo

A working, tested implementation — not a mockup, not a pile of stubs.
The full pipeline runs end-to-end: GPS ingestion map-matches and
persists pings, triggers event detection in the background, matches
behavioral signatures against known event patterns, reasons over
neighboring segments, and serves results with a computed alternate
route. **17 tests pass**, including a full integration test that posts
realistic GPS traffic and asserts a real detected event comes back out
of the API. The system now uses a **PyTorch MLP as the primary event
classifier** (trained via federated learning across 8 regional silos)
with the original rule-based matcher as a cold-start fallback.

What's still simplified or stubbed is clearly marked with `TODO`
comments and explained in `docs/architecture.md`'s "what's real vs.
what's a stub" section — nothing is silently fake.

Deployment (Docker/docker-compose) was deliberately left out of this
pass to focus on getting the actual logic right first — see
`CLAUDE.md`'s backlog for adding it back.

```
fedrouteai/
├── backend/            FastAPI service — API, services, DB models, ML pipeline
├── frontend/            React + Leaflet dashboard
├── federated_clients/   Per-region Flower client runner + configs
├── scripts/              Dataset generation + DB seeding
├── docs/                  Architecture, data models, API contract, event signatures
├── data/                  Generated datasets land here (gitignored except structure)
├── about_project.md       Full file-by-file tour of this repo
└── CLAUDE.md              Context file for AI coding tools — READ THIS before generating code
```

`backend/app/ml/` — ML subsystem added in Phase 2:
```
app/ml/
├── features/     datasource abstraction, sliding-window extraction, 7-stage pipeline
├── training/     class weights, replay buffer, XGBoost baseline, MLP, evaluation
├── models/       BaseLocalModel ABC
└── artifacts/    baseline/, federated/, metrics/, feature_tables/ (gitignored)
```

## Quickstart (no Docker — plain Postgres + local processes)

### 1. Start Postgres with PostGIS
Use whatever you have locally — e.g. an existing Postgres install with
the postgis extension available, or a one-off container:
```bash
docker run -d --name fedrouteai-db -e POSTGRES_DB=fedrouteai \
  -e POSTGRES_USER=fedrouteai -e POSTGRES_PASSWORD=fedrouteai \
  -p 5432:5432 postgis/postgis:16-3.4
```
(That's the only Docker usage here — a throwaway DB container, not part
of the application. Swap in any Postgres+PostGIS instance you already
have.)

### 2. Install dependencies
```bash
python3 -m venv .venv && source .venv/bin/activate
pip install -r backend/requirements.txt
cp backend/.env.example backend/.env    # edit if your DB isn't the default above
```

### 3. Generate the synthetic dataset + seed the DB
```bash
./scripts/generate_dataset_then_seed.sh
```
This creates ~130 road segments across 8 regions, ~490K labeled GPS
pings, and 7 types of injected events (congestion, road_block,
road_damage, construction, flood, accident, diversion) — see
`scripts/dataset_generator/` and `docs/event_signatures.md`.

### 4. Run the backend
```bash
cd backend && PYTHONPATH=. uvicorn app.main:app --reload
```
Visit `http://localhost:8000/docs` for interactive API docs.

### 5. Run the tests
```bash
cd backend && PYTHONPATH=. pytest tests/ -v
```
All 17 tests pass without needing a database running — they use
in-memory SQLite / plain objects (see `docs/architecture.md` for why
that matters and how the DB-backed integration test is wired).

### 6. Run the frontend
```bash
cd frontend && npm install && npm run dev
```

### 7. Run federated learning (separate from the steps above)
```bash
# terminal 1
cd backend && PYTHONPATH=. python3 -m app.services.federated_learning.flower_server

# terminals 2-9 (one per region)
python3 federated_clients/run_client.py --region REGION_01
python3 federated_clients/run_client.py --region REGION_02
# ... through REGION_08
```

## Tech stack

| Layer | Choice |
|---|---|
| API | FastAPI |
| DB | PostgreSQL + PostGIS |
| ORM / migrations | SQLAlchemy + Alembic |
| Federated learning | Flower + AdaptiveFedAvg (5-factor weighted aggregation) |
| Graph / routing | NetworkX |
| ML (federated) | PyTorch MLP (primary classifier after FL training) |
| ML (baseline) | XGBoost (centralized baseline, research comparison) |
| GIS (future real-data swap-in) | OSMnx, GeoPandas, Shapely |
| Frontend | React + Leaflet |
| Testing | pytest, in-memory SQLite integration tests |

## Where to go next

- **New to this repo?** Read `about_project.md` for a full file-by-file
  tour, then `docs/architecture.md` for the design rationale and exactly
  what's real vs. simplified.
- **Continuing development with an AI coding tool** (Claude Code, etc.)?
  Read `CLAUDE.md` — it has the working conventions and a prioritized
  backlog so the tool doesn't have to rediscover the architecture from
  scratch every session.
- **Adding a new event type?** One new entry in
  `backend/app/services/event_detection/event_signatures.py`, plus a
  matching entry in `scripts/dataset_generator/event_signatures.py` (kept
  in sync manually — see `docs/data_models.md`).
- **Swapping in a real city's road network?** Replace
  `scripts/dataset_generator/road_network.py::build_road_network()`'s
  output with an `osmnx.graph_from_place(...)` pull — every downstream
  file only depends on the `segments.csv` column schema, documented in
  `docs/data_models.md`.
