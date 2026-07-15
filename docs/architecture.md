# FedRouteAI — Architecture

Layered / service-oriented backend (FastAPI doesn't have a built-in MVC,
so this is the closest sane mapping — think "Controller → Service →
Repository → Model" rather than classic Rails-style MVC):

```
Request
   │
   ▼
API layer (app/api/v1/endpoints/*)         <- "Controllers": parse request,
   │                                          call one service, return response.
   │                                          No business logic lives here.
   ▼
Service layer (app/services/*)             <- All business logic. Pure-ish
   │                                          functions/classes, easy to unit
   │                                          test without a DB (see tests/).
   ▼
Repository layer (app/repositories/*)      <- Only layer allowed to write
   │                                          SQLAlchemy queries. Services
   │                                          never touch a DB Session directly.
   ▼
Model layer (app/models/*)                 <- SQLAlchemy ORM — the DB schema.
                                               app/schemas/* is the SEPARATE
                                               Pydantic API contract layer —
                                               deliberately not the same classes.
```

## Why this split (not just "put everything in main.py")

- **Services are testable without a database.** `tests/test_event_detection.py`
  and `tests/test_routing.py` never touch SQL — they pass in plain
  objects. This matters a lot once you're iterating on the actual
  intelligence (event signatures, routing costs) — you want that
  feedback loop to be milliseconds, not "spin up Postgres."
- **Repositories isolate the one thing likely to change**: how data is
  stored. If a table becomes a materialized view, or a query needs to
  move to raw SQL for performance, only the repository changes.
- **Schemas vs. Models are separate on purpose.** The DB schema and the
  API contract WILL diverge over time (e.g. you'll want to hide
  internal columns, or the frontend wants nested objects the DB
  doesn't store that way) — decoupling them now avoids a payful
  refactor later.

## The pipeline, mapped to code

| Project spec stage | Code |
|---|---|
| GPS ingestion | `api/v1/endpoints/ingest.py` (full: match → persist → trigger detection) |
| Map matching | `services/map_matching/matcher.py` (geometric projection + trajectory continuity) |
| Road segment graph | `services/road_graph/graph_builder.py`, cached via `graph_cache.py` |
| Historical road memory | `services/historical_memory/aggregator.py` (pure fn) + `builder.py` (DB orchestration, event-window exclusion) |
| Federated learning (local + global) | `services/federated_learning/*` + `federated_clients/` |
| Event memory matching | `services/event_detection/*`, tied together by `orchestrator.py` |
| Graph reasoning (neighbor analysis) | `services/road_graph/neighbor_reasoning.py` |
| Route optimization | `services/routing/*` |
| Structured JSON output | `schemas/event.py::EventOut`, served via `api/v1/endpoints/events.py` (populates `recommended_route` for real) |

## Federated learning topology

This is NOT a single process. Three independent things run:

1. **`backend/`** — the central API + DB. Does NOT do FL training itself;
   it serves the aggregated results (`api/v1/endpoints/federated.py`).
2. **Flower server** (`app/services/federated_learning/flower_server.py`)
   — coordinates aggregation rounds using `AdaptiveFedAvg`.
3. **Flower clients** (`federated_clients/run_client.py`, one process per
   region) — train locally, send only weight updates to the server.
   Raw GPS/trajectory data never leaves the client process.

## What's real vs. what's a stub, honestly

Real, tested, working — including full integration tests, not just
unit tests:
- **Full ingest -> detect -> serve loop**: `POST /ingest/gps` map-matches
  incoming pings (real geometric projection + trajectory continuity),
  persists them, and triggers `event_detection/orchestrator.py` as a
  background task, which extracts a behavioral signature, matches it
  against the Event Memory patterns, runs graph reasoning over
  neighbors, and writes an `Event` row if confidence clears the
  threshold. `tests/test_ingest_and_detection.py` posts realistic
  congestion-shaped traffic and asserts a real event comes back out of
  `GET /events` with the right type and confidence — this is proven
  end-to-end, not just plumbing-verified.
- **Historical memory builder** (`historical_memory/builder.py`) —
  aggregates GPS pings into per-segment-per-hour baselines, explicitly
  excluding pings that fall inside a known event window so an ongoing
  construction event doesn't slowly get absorbed into "normal."
- **Map matching** — real point-to-segment geometric projection (not
  sampling) plus trajectory continuity (a vehicle's previous match
  biases disambiguation of the next one) — see
  `tests/test_map_matching.py` for a calibrated near-tie test proving
  the continuity bonus actually changes the outcome.
- **Event signature matching** — tolerance-weighted, Gaussian-falloff
  distance metric calibrated so realistically noisy small-sample live
  signatures still match (not just exact-target self-matching).
- **Adaptive federated aggregation** — all 5 weighting factors from the
  project brief computed for real: data_quality, event_confidence (from
  live detected events in that region), historical_similarity (cosine
  similarity against that region's own previous round, tracked in
  `FLRoundRecord`), temporal_recency (decays with data staleness), and
  regional_relevance (normalized by segment count against the largest
  region in that round). See `tests/test_adaptive_aggregation.py`.
- **Graph caching** — the road graph is built once (at startup or first
  use) and cached; only event penalties are recomputed per routing
  request, not the whole graph.
- **`/events` populates `recommended_route`** by routing between the
  affected segment's neighbors, avoiding every currently-active event.
- Road graph construction, Dijkstra/A* routing with event-penalty
  repricing, all ORM models + repositories + Pydantic schemas, dataset
  generation + DB seeding.

Two real bugs worth knowing about, found and fixed during this build
(both have regression tests now): historical memory's
`avg_vehicle_count` was originally a raw multi-day total instead of a
true per-hour average (`test_avg_vehicle_count_is_per_hour_not_a_multi_day_total`),
and `GPSPingIn` originally had a redundant, unused per-ping `device_id`
field that silently diverged from the batch-level one — removed, since
a batch is one device's trajectory by design.

Working but intentionally simple (flagged in the code, not hidden):
- **FL local model** (`local_model.py`) — a learned Gaussian baseline per
  region, not a neural net. This is deliberate: it's the simplest thing
  that makes FedAvg-style parameter averaging meaningful (means/stds
  average sensibly) and keeps the whole pipeline runnable without a
  GPU. `flower_client.py` now loads REAL signature data via the
  repository layer when a region has enough history, falling back to
  clearly-flagged synthetic padding only during cold start.
- **Event severity** is currently a proxy equal to confidence — no
  dedicated severity signal exists yet (noted in `orchestrator.py`).

Structural stubs, clearly marked:
- Event `end_time` isn't updated once an event stops recurring — events
  are written once and never "closed out." A periodic job that checks
  whether a segment's signature has returned to baseline and closes the
  event would be the natural next piece.
- `ingest.py` uses FastAPI `BackgroundTasks` (in-process), not a
  queue/broker — a deliberate Phase 1 scope decision, noted in the
  file, with a small and localized change needed to swap it out.
