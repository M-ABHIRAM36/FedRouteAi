# About FedRouteAI

> **Status update**: verified running end-to-end against a real local
> PostgreSQL 18 + PostGIS instance — 130 segments / 8 regions / 491,370
> GPS pings generated, `regions`/`segments`/`segment_historical_memory`/
> `events` seeded and confirmed (8/130/3,035/23 rows respectively),
> graph cache built (130 nodes, 622 edges), all 17 tests passing,
> `/health`/`/segments`/`/segments/{id}`/`/segments/{id}/neighbors`
> confirmed working. `gps_pings` bulk-load via ORM intentionally
> skipped per the TODO in `seed_db.py` (use Postgres `COPY` instead).
>
> **Current top priority**: the pipeline is real and tested, but the
> "intelligence" layer is still rule-based (hand-written event
> signatures) and the federated model is a closed-form statistic
> (mean/std), not a trained classifier. **Read `CLAUDE.md`'s "CURRENT
> TOP PRIORITY" section before doing anything else** — it has the full
> reasoning, model choice (MLP over XGBoost, and why), pipeline, and a
> 6-milestone roadmap to make this a genuinely learned federated system.

## What this project is

FedRouteAI is a real-time road-event detection system. It watches GPS
traffic patterns on individual road segments, learns what "normal"
looks like for each segment at each hour of day using **privacy-preserving
federated learning** (raw GPS never leaves a region — only model weight
updates do), and detects temporary events — construction, flooding,
accidents, road closures, congestion, road damage, diversions — by
comparing live behavior against both a segment's own history and a
library of known event "signatures." A lightweight graph-reasoning
layer checks whether neighboring road segments corroborate a detected
anomaly, and a routing layer recomputes alternate paths around
confirmed events. The system doesn't replace a navigation app — it's
the detection layer that would feed one.

## Is this a working system?

Yes, with an honest scope. The full pipeline — ingest a GPS batch, map
it onto the correct road segment, persist it, detect whether it looks
like a known event pattern, corroborate against neighboring segments,
and serve the result with a computed alternate route — runs end to end
and is proven by an integration test, not just unit tests in isolation.
17 tests pass. Two real bugs were found and fixed during development
(both now have regression tests guarding them — see
`docs/architecture.md` for details). What's intentionally simplified
(the FL model architecture, the map matcher's algorithm, event
close-out) is documented plainly rather than hidden — see
`docs/architecture.md`'s "what's real vs. what's a stub" section and
`CLAUDE.md`'s backlog.

Deployment tooling (Docker, docker-compose) was deliberately left out
of this pass to keep the focus on correctness; see `CLAUDE.md` for
adding it back.

---

## Full directory tree

```
fedrouteai/
├── about_project.md
├── CLAUDE.md
├── README.md
├── .gitignore
│
├── backend/
│   ├── .env.example
│   ├── alembic.ini
│   ├── requirements.txt
│   ├── alembic/
│   │   ├── env.py
│   │   └── versions/                          (empty — no migrations generated yet)
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   ├── constants.py
│   │   │   └── logging_config.py
│   │   ├── db/
│   │   │   ├── base.py
│   │   │   ├── session.py
│   │   │   └── init_db.py
│   │   ├── models/
│   │   │   ├── region.py
│   │   │   ├── segment.py
│   │   │   ├── gps_ping.py
│   │   │   ├── event.py
│   │   │   ├── historical_memory.py
│   │   │   └── fl_round_record.py
│   │   ├── schemas/
│   │   │   ├── segment.py
│   │   │   ├── gps_ping.py
│   │   │   ├── event.py
│   │   │   ├── route.py
│   │   │   └── federated.py
│   │   ├── repositories/
│   │   │   ├── base_repository.py
│   │   │   ├── segment_repository.py
│   │   │   ├── gps_repository.py
│   │   │   ├── event_repository.py
│   │   │   ├── historical_memory_repository.py
│   │   │   ├── region_repository.py
│   │   │   └── fl_round_repository.py
│   │   ├── services/
│   │   │   ├── map_matching/
│   │   │   │   └── matcher.py
│   │   │   ├── road_graph/
│   │   │   │   ├── graph_builder.py
│   │   │   │   ├── graph_cache.py
│   │   │   │   └── neighbor_reasoning.py
│   │   │   ├── historical_memory/
│   │   │   │   ├── aggregator.py
│   │   │   │   └── builder.py
│   │   │   ├── event_detection/
│   │   │   │   ├── event_signatures.py
│   │   │   │   ├── signature_extractor.py
│   │   │   │   ├── pattern_matcher.py
│   │   │   │   └── orchestrator.py
│   │   │   ├── federated_learning/
│   │   │   │   ├── local_model.py
│   │   │   │   ├── global_model.py
│   │   │   │   ├── flower_client.py
│   │   │   │   ├── flower_server.py
│   │   │   │   └── adaptive_aggregation.py
│   │   │   └── routing/
│   │   │       ├── cost_model.py
│   │   │       └── path_finder.py
│   │   ├── api/v1/
│   │   │   ├── router.py
│   │   │   └── endpoints/
│   │   │       ├── health.py
│   │   │       ├── segments.py
│   │   │       ├── ingest.py
│   │   │       ├── events.py
│   │   │       ├── routes.py
│   │   │       └── federated.py
│   │   ├── ml/artifacts/                       (empty — trained model weights land here)
│   │   └── utils/
│   │       ├── geo_utils.py
│   │       └── time_utils.py
│   └── tests/
│       ├── conftest.py
│       ├── test_api_health.py
│       ├── test_map_matching.py
│       ├── test_event_detection.py
│       ├── test_historical_memory.py
│       ├── test_adaptive_aggregation.py
│       ├── test_routing.py
│       └── test_ingest_and_detection.py
│
├── federated_clients/
│   ├── run_client.py
│   └── region_config/
│       └── region_01.yaml … region_08.yaml
│
├── frontend/
│   ├── package.json
│   ├── vite.config.js
│   ├── index.html
│   └── src/
│       ├── main.jsx
│       ├── App.jsx
│       ├── api/client.js
│       ├── components/
│       │   ├── MapView.jsx
│       │   ├── EventFeed.jsx
│       │   └── SegmentDetail.jsx
│       └── pages/
│           └── Dashboard.jsx
│
├── scripts/
│   ├── dataset_generator/
│   │   ├── geo_utils.py
│   │   ├── road_network.py
│   │   ├── traffic_sim.py
│   │   ├── event_signatures.py
│   │   └── generate_dataset.py
│   ├── seed_db.py
│   ├── generate_dataset_then_seed.sh
│   └── run_dev.sh
│
├── docs/
│   ├── architecture.md
│   ├── data_models.md
│   ├── api_contract.md
│   └── event_signatures.md
│
└── data/
    ├── raw/                                    (generated dataset lands here, gitignored)
    └── processed/                              (gitignored)
```

---

## File-by-file guide

### Root

| File | What it does |
|---|---|
| `README.md` | Quickstart: how to install, generate data, run the backend/frontend/tests/FL cluster. Start here to *run* the project. |
| `CLAUDE.md` | Context file for AI coding tools (Claude Code, etc.): architecture rules, conventions, an honest current-state summary, and a prioritized backlog. Start here to *continue building* the project, especially with AI assistance. |
| `about_project.md` | This file — the full tour. |
| `.gitignore` | Excludes `__pycache__`, `.env`, `node_modules`, generated datasets, build output, and model artifacts from version control. |

### `backend/` — the FastAPI service

| File | What it does |
|---|---|
| `requirements.txt` | All Python dependencies: FastAPI, SQLAlchemy, Alembic, Flower, NetworkX, scikit-learn/XGBoost, OSMnx/GeoPandas/Shapely (for a future real-map swap-in), pytest. |
| `.env.example` | Template for local DB connection settings — copy to `.env` and edit. |
| `alembic.ini`, `alembic/env.py` | Database migration tooling config, wired to the app's settings and models so `alembic revision --autogenerate` picks up schema changes automatically. `alembic/versions/` is empty until you generate your first migration. |

**`app/core/`** — cross-cutting configuration, used by every other layer
- `config.py` — the single `Settings` object (env-driven): DB connection, city center coordinates, map-matching tolerance, event confidence threshold, FL round counts, routing penalty factor. Nothing else in the codebase should hardcode these values.
- `constants.py` — shared enums: `EventType`, `VehicleType`, `RoadType`, `RoadDirection`. Import from here instead of restringing literals.
- `logging_config.py` — one `get_logger(name)` used everywhere instead of bare `print()`.

**`app/db/`** — database plumbing
- `base.py` — the SQLAlchemy declarative base every model inherits from.
- `session.py` — engine + session factory + the `get_db()` FastAPI dependency that hands a DB session to a request and guarantees it closes.
- `init_db.py` — creates all tables and enables the PostGIS extension; used for fast local bring-up (Alembic should own schema changes after your first migration).

**`app/models/`** — SQLAlchemy ORM (the database schema)
- `region.py` — one federated-learning silo: `region_id`, `pincode`, center coordinates, segment count.
- `segment.py` — the fundamental unit of the whole system: the road between two intersections. Geometry, lane count, width, speed limit, direction, flood-proneness, and a semicolon-joined list of neighboring segment IDs.
- `gps_ping.py` — one raw, map-matched GPS observation: position, speed, heading, timestamp, U-turn flag, and (for synthetic/training data only) a ground-truth label.
- `event.py` — a detected (or ground-truth) road event: type, confidence, severity, time window, affected neighbors, and whether it came from live detection or synthetic injection.
- `historical_memory.py` — the per-segment, per-hour-of-day "normal" baseline: average speed/std/vehicle count/U-turn rate that everything else compares against.
- `fl_round_record.py` — one region's contribution to one federated-learning aggregation round (data quality, loss, sample count, feature-mean vector, data freshness) — what lets adaptive aggregation compare a region against its own history.

**`app/schemas/`** — Pydantic API contract (deliberately separate from the DB models — see `docs/architecture.md` for why)
- `segment.py` — `SegmentOut`, what `/segments` returns.
- `gps_ping.py` — `GPSPingIn`/`GPSBatchIn`, what a mobile client POSTs to `/ingest/gps`. No per-ping `device_id` by design — a batch is one device's trajectory.
- `event.py` — `EventOut`, the literal JSON contract from the original project spec (`segment_id`, `event`, `confidence`, `affected_neighbors`, `recommended_route`).
- `route.py` — `RouteRequest`/`RouteResponse` for `/routes`.
- `federated.py` — admin/observability schemas for FL status endpoints.

**`app/repositories/`** — the only layer allowed to write database queries
- `base_repository.py` — generic CRUD (`get`, `list_all`, `add`, `add_all`) so per-entity repositories don't repeat boilerplate.
- `segment_repository.py` — segment lookups by region, neighbor resolution, and `get_candidates_near()` — a bounding-box spatial prefilter used by map matching.
- `gps_repository.py` — recent-pings lookup for signature extraction, hour-of-day windowed lookup for historical memory building, and bulk insert for ingestion.
- `event_repository.py` — active-event lookups, used by routing (to penalize edges) and events serving.
- `historical_memory_repository.py` — baseline lookup and upsert (update-in-place if a segment/hour row already exists).
- `region_repository.py` — simple region lookups (used by the FL client to report `regional_relevance`).
- `fl_round_repository.py` — records and retrieves each region's per-round FL contribution history.

**`app/services/`** — all business logic, organized to mirror the project's pipeline stages

- `map_matching/matcher.py` — converts raw `(lat, lon)` into a `segment_id`. Uses real point-to-line-segment geometric projection (not point-sampling) plus **trajectory continuity**: a vehicle's previous match biases the next match toward connected segments, which is what actually disambiguates parallel roads and intersections. Includes a documented, tested upgrade path to a dedicated map-matching library (FMM/OSRM) for noisier real-world GPS.

- `road_graph/graph_builder.py` — builds the NetworkX directed graph of the road network: nodes are segments (not intersections, matching the project's segment-as-fundamental-unit design), edges connect segments that share an intersection, weighted by travel time.
- `road_graph/graph_cache.py` — caches that graph's *structure* (built once at startup or first use) since only edge *weights* change when events start/end — those get repriced cheaply per request instead of rebuilding the whole graph from the database every time.
- `road_graph/neighbor_reasoning.py` — the lightweight Graph Reasoning layer: given a flagged segment, checks whether neighboring segments' behavior corroborates it, and adjusts confidence accordingly. Deliberately simple (a corroboration-ratio heuristic), not a GNN, matching the project's stated scope.

- `historical_memory/aggregator.py` — pure function: turns a list of GPS pings into one hourly baseline (average speed, std, vehicle count, U-turn rate). Vehicle count is normalized to a true per-hour figure (divided by distinct days observed) — an earlier version of this got that wrong; there's a regression test for it now.
- `historical_memory/builder.py` — the database-facing orchestration around the aggregator: fetches a segment's pings for an hour-of-day bucket across a lookback window, **excludes any pings that fall inside a known event's time window** (so an ongoing construction event doesn't slowly get absorbed into "normal"), and upserts the result.

- `event_detection/event_signatures.py` — the single source of truth for what each of the 7 event types "looks like": multipliers on a segment's own baseline for speed, density, U-turn rate, and speed variance, plus how much spillover neighboring segments absorb. Reused unchanged by the synthetic dataset generator (`scripts/dataset_generator/`), so training data and live detection can never silently drift apart.
- `event_detection/signature_extractor.py` — turns a live window of recent pings + a segment's baseline into a `BehavioralSignature` (ratios relative to baseline), correctly scaling the baseline's per-hour density expectation down to match however long the live window actually is.
- `event_detection/pattern_matcher.py` — compares a live signature against every event signature and returns the closest match + a confidence score. Uses a **per-feature noise tolerance** (not a single flat distance threshold) because some features — especially U-turn rate on a small sample — are inherently noisier than others; this was tuned against realistic small-sample data, not just exact-match self-tests.
- `event_detection/orchestrator.py` — the piece that actually runs signature extraction, pattern matching, and graph reasoning together against the database and writes an `Event` row when confidence clears the threshold. This is what `ingest.py` triggers after persisting new pings.

- `federated_learning/local_model.py` — what each region trains: a learned Gaussian baseline (mean/std) over behavioral-signature features. Deliberately simple — it's the smallest model for which FedAvg-style parameter averaging is meaningful, and it keeps the whole pipeline runnable without a GPU.
- `federated_learning/global_model.py` — holds the current aggregated global parameters server-side; regions with too little local data can fall back to this (standard FL cold-start handling).
- `federated_learning/flower_client.py` — the Flower `NumPyClient` run once per region. Loads **real** training data via the repository layer (signature vectors from that region's own segments) when enough history exists, falling back to clearly-flagged synthetic padding only during cold start.
- `federated_learning/flower_server.py` — entry point that starts the Flower server with the custom adaptive strategy.
- `federated_learning/adaptive_aggregation.py` — extends Flower's `FedAvg` to weight each region's update by all five factors named in the project brief: data quality, event confidence (from that region's live detected events), historical similarity (cosine similarity against that region's *own* previous round), temporal recency (decays with data staleness), and regional relevance (normalized by segment count).

- `routing/cost_model.py` — applies event penalties to the graph (`current_travel_time = base_travel_time × penalty_factor`) as specified in the project brief, returning a repriced copy rather than mutating the cached graph.
- `routing/path_finder.py` — thin, well-tested wrappers around NetworkX's Dijkstra and A* (A* needs per-node coordinates to be attached for its heuristic to activate; falls back to Dijkstra-equivalent behavior otherwise).

**`app/api/v1/`** — the HTTP layer (thin — parses requests, calls a service/repository, returns a response)
- `router.py` — aggregates every endpoint module into one router.
- `endpoints/health.py` — liveness check.
- `endpoints/segments.py` — list/get segments and their neighbors.
- `endpoints/ingest.py` — **the full ingestion pipeline**: spatially prefilters candidate segments, map-matches the batch, persists matched pings, and schedules background event detection for every touched segment.
- `endpoints/events.py` — lists active events, computing a real `recommended_route` for each by routing between its affected neighbors around all currently-active events.
- `endpoints/routes.py` — computes a route using the cached graph, penalizing active-event segments by default; also exposes a manual cache-refresh endpoint.
- `endpoints/federated.py` — read-only observability into the FL subsystem's current round.

- `app/main.py` — the FastAPI app itself: CORS, router mounting, and a startup lifespan that warms the graph cache (tolerating a not-yet-ready database rather than crashing).
- `app/utils/geo_utils.py` — the meters↔degrees conversion used everywhere a point gets placed or projected: latitude degrees are ~constant everywhere (~111,320m), longitude degrees shrink by `cos(latitude)` — this file is why that's handled correctly instead of with a flat epsilon.
- `app/utils/time_utils.py` — a centralized `utcnow()` (naive UTC, matching this project's plain `DateTime` columns) plus hour-of-day/peak-hour helpers.
- `app/ml/artifacts/` — empty directory where trained model weights would be saved, if/when the FL local model grows beyond the in-memory Gaussian baseline.

**`backend/tests/`** — 17 tests, all passing
- `conftest.py` — two fixtures: `db_session` (bare in-memory SQLite for unit tests) and `client` (a full FastAPI `TestClient` wired to a *shared* in-memory SQLite DB via dependency override, so a test can POST to an endpoint and then GET the result of a background task in the same test).
- `test_api_health.py` — the app boots and responds.
- `test_map_matching.py` — nearest-segment matching, no-confident-match handling, and two tests proving trajectory continuity actually changes the outcome on a calibrated near-tie.
- `test_event_detection.py` — every one of the 7 event signatures round-trips through the matcher correctly; a "normal" signature doesn't falsely trigger.
- `test_historical_memory.py` — regression test for the per-hour-average bug, and a test proving the builder correctly excludes pings inside a known event window.
- `test_adaptive_aggregation.py` — the historical-similarity and temporal-recency weighting functions behave correctly at their edge cases (no history yet, identical vectors, divergent vectors, fresh vs. stale data).
- `test_routing.py` — an event penalty measurably increases route cost.
- `test_ingest_and_detection.py` — **the full integration test**: seeds a tiny road network and baseline directly into the test database, POSTs realistic congestion-shaped GPS traffic (calibrated to the congestion signature's actual target multipliers), and asserts a real `Event` with the right type and confidence comes back out of `GET /events`.

### `federated_clients/` — per-region FL client processes

- `run_client.py` — launches one Flower client for one region; run once per region against a running Flower server.
- `region_config/region_0X.yaml` — per-region config placeholders (currently minimal — region ID is passed via CLI flag; these exist for whatever needs to differ per region beyond that, e.g. isolated per-region infrastructure).

### `frontend/` — React + Leaflet dashboard

- `package.json`, `vite.config.js`, `index.html` — standard Vite/React project setup; the dev server proxies `/api` to the backend.
- `src/api/client.js` — thin Axios wrapper around the backend's v1 API.
- `src/components/MapView.jsx` — renders road segments as colored polylines on a Leaflet map, coloring segments involved in an active event by event type.
- `src/components/EventFeed.jsx` — a live-feed sidebar list of active events.
- `src/components/SegmentDetail.jsx` — placeholder detail panel for a clicked segment (not yet wired to click events — noted as a TODO in the file).
- `src/pages/Dashboard.jsx` — the main page: fetches segments + active events and lays out the map + event feed.
- `src/App.jsx`, `src/main.jsx` — standard React app entry points.

### `scripts/` — dataset generation and DB seeding

- `dataset_generator/geo_utils.py` — the same meters↔degrees conversion as the backend's copy (kept separate on purpose since this script has no dependency on the backend package).
- `dataset_generator/road_network.py` — builds a synthetic-but-geospatially-real road network (anchored at real Hyderabad coordinates, realistic block spacing, irregular layout) since this sandbox has no internet access to the OpenStreetMap Overpass API; documented as a drop-in-replaceable stand-in for a real `osmnx.graph_from_place(...)` pull.
- `dataset_generator/traffic_sim.py` — simulates GPS pings per segment per hour under normal or event conditions, respecting realistic constraints (speed floors/ceilings, day/night/peak profiles, vehicle-type-adjusted speeds).
- `dataset_generator/event_signatures.py` — the same signature table as the live backend's copy, used to generate labeled training data that matches exactly what the detector looks for.
- `dataset_generator/generate_dataset.py` — orchestrates the above into the full dataset: ~130 segments / 8 regions / ~490K labeled GPS pings / 23 ground-truth events, written as both a "global" (centralized) view and a "federated" (per-region) split.
- `seed_db.py` — loads the generated CSVs into the real database via the ORM models.
- `generate_dataset_then_seed.sh`, `run_dev.sh` — convenience shell scripts chaining the above / running backend+frontend locally.

### `docs/` — design documentation

- `architecture.md` — the layering rationale, a pipeline-stage-to-code mapping table, and an honest, itemized account of what's real/tested vs. simplified vs. stubbed (including the two real bugs found and fixed during development).
- `data_models.md` — why the ORM and Pydantic schema layers are kept separate, a summary of every model, and how the synthetic dataset's columns map onto them.
- `api_contract.md` — every endpoint, its status, and the exact JSON shape of the core `EventOut` object.
- `event_signatures.md` — the full table of event-type multipliers, explained.

### `data/`

Empty except `.gitkeep` placeholders — this is where `generate_dataset_then_seed.sh` writes the synthetic dataset (`data/raw/fedrouteai_dataset/`) and where any future processed/derived data would land. Gitignored so the repo itself stays small; regenerate anytime with `scripts/dataset_generator/generate_dataset.py`.
