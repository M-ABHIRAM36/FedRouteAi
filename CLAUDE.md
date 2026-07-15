# CLAUDE.md — context for AI coding tools continuing this project

Read this before generating code anywhere in this repo. It exists so
every session (or every tool — Claude Code, Cursor, whatever) builds on
the same conventions instead of re-deriving them, or worse, drifting.

## What this project is

FedRouteAI detects temporary road events (construction, flood,
accidents, closures, etc.) from GPS traffic patterns using federated
learning, then reroutes around them. Full design rationale:
`docs/architecture.md`. Read that file too, not just this one.

## Architecture rules — do not violate these

1. **Layering is one-directional**: `api/` → `services/` → `repositories/`
   → `models/`. An endpoint file may import a service. A service may
   import a repository. A repository may import a model. Never the
   reverse, and never skip a layer (an endpoint must not import a
   repository directly, a service must not import SQLAlchemy Session
   itself).
2. **Business logic lives in `services/`, nowhere else.** Endpoint
   functions in `api/v1/endpoints/*.py` should be thin: parse request →
   call a service or repository → return. If you're writing an `if`
   statement that encodes a domain rule inside an endpoint file, move it
   to a service.
3. **`app/schemas/` (Pydantic, API contract) and `app/models/` (SQLAlchemy,
   DB schema) stay separate classes**, even when their fields look
   identical today. Do not collapse them.
4. **Every new service function should be callable and testable without
   a database.** Pass in plain data (or repository results already
   fetched), return plain data. Look at `services/event_detection/` and
   `services/routing/` for the pattern; `tests/test_event_detection.py`
   and `tests/test_routing.py` show these being tested with zero DB
   setup.
5. **`event_signatures.py` is duplicated on purpose** between
   `backend/app/services/event_detection/` (live matcher) and
   `scripts/dataset_generator/` (training data generator). If you change
   one, change the other, or the model will be validated against
   patterns it wasn't trained to recognize. This is the one intentional
   exception to "don't duplicate code" in this repo — see
   `docs/data_models.md` for why.

## Conventions

- Python 3.12, type hints everywhere (`list[X]` not `List[X]`,
  `X | None` not `Optional[X]`).
- Config always through `app.core.config.settings` — never
  `os.environ.get(...)` scattered in service code.
- Logging via `app.core.logging_config.get_logger(__name__)`, not bare
  `print()` or `logging.getLogger()`.
- Constants/enums (event types, vehicle types, road types) live in
  `app.core.constants` — import from there, don't restring literals.
- New DB columns → update the SQLAlchemy model, then
  `alembic revision --autogenerate -m "..."`, then update
  `docs/data_models.md`'s column description if the meaning isn't obvious.
- New tests go in `backend/tests/`, named `test_<module>.py`, following
  the existing fixture-free style where possible (see rule 4 above).

## Before you consider a change done

```bash
cd backend
PYTHONPATH=. python3 -m pytest tests/ -v      # must pass, including any new tests you added
PYTHONPATH=. python3 -c "from app.main import app"   # must import cleanly
```
If you touched `services/routing/` or `services/road_graph/`, also
sanity check with the inline smoke-test pattern used during this repo's
initial build (build a few fake `SimpleNamespace` segments, build the
graph, run a query) rather than trusting it compiles.

## Current state (accurate as of this build)

**Real, tested, working end-to-end** — including a full integration
test (`tests/test_ingest_and_detection.py`) that posts realistic GPS
traffic and asserts a real `Event` comes back out of `GET /events`:
- Full ingest → map-match → persist → detect → serve loop
- Map matching: real geometric projection + trajectory continuity
- Historical memory builder: aggregates pings into baselines, excludes
  known-event windows
- Event signature matching: tolerance-weighted, calibrated for
  realistic noisy small-sample signatures (not just exact-match)
- Graph reasoning, Dijkstra/A* routing with event-penalty repricing,
  graph caching (built once, not per-request)
- Adaptive federated aggregation: all 5 brief-specified weighting
  factors computed for real (see `docs/architecture.md`)
- `/events` populates `recommended_route` for real
- 17 passing tests across map matching, event detection, routing,
  historical memory, adaptive aggregation, and the full ingest loop

**Two real bugs found and fixed during this build** (both have
regression tests): historical memory's `avg_vehicle_count` was
originally a multi-day total instead of a true per-hour average; and
`GPSPingIn` had a redundant, silently-unused per-ping `device_id` field
that has been removed (a batch is one device's trajectory by design).

**Working but intentionally simple:** FL local model is a Gaussian
baseline, not a neural net (deliberate — see `local_model.py`);
`flower_client.py` loads real signature data via the repository layer
when history exists, with clearly-flagged synthetic padding only for
cold start.

**Structural stubs, clearly marked:** events don't get an `end_time`
update once they stop recurring (no "close out" pass yet); ingestion
uses in-process `BackgroundTasks`, not a queue/broker (deliberate Phase
1 scope decision).

## Prioritized backlog

Roughly in the order that unblocks the most other work:

1. **Event close-out pass**: a periodic job that checks whether a
   segment's live signature has returned to baseline and updates the
   corresponding `Event.end_time` — right now events are written once
   and never marked as resolved.
2. **Swap the map matcher** for FMM (`fast-map-matching`) or OSRM's
   `/match` once you're testing against real (noisier) GPS instead of
   clean synthetic points — the current geometric + continuity matcher
   is solid for Phase 1 but a dedicated HMM-based matcher will do better
   at real-world noise levels and complex intersections.
3. **Real road network**: replace
   `scripts/dataset_generator/road_network.py`'s synthetic grid with an
   `osmnx.graph_from_place("Hyderabad, India")` pull once you have
   internet access in whatever environment runs this (this sandbox
   didn't, which is why the network is synthetic-but-geospatially-real
   — see that file's module docstring).
4. **Deployment**: Docker/docker-compose were deliberately left out of
   this pass to focus on correctness first — add them back once the
   core logic is where you want it (the previous scaffold had a working
   docker-compose for Postgres+PostGIS+backend+frontend as a reference).
5. **Move ingestion off in-process BackgroundTasks** to a real
   queue/broker (Celery/RQ) once you need this to scale past one
   process — the orchestrator function itself (`detect_and_record_event`)
   doesn't change, only what calls it.
6. **Event severity** currently proxies confidence 1:1 — a dedicated
   severity signal (e.g. derived from how far the signature deviates,
   not just how confidently it matches a pattern) would be more
   informative once you have real incident data to calibrate against.

## Things NOT to do

- Don't add a second ORM/query layer bypassing `repositories/` "just this
  once for performance" — if performance is genuinely the issue, put the
  raw SQL inside the repository method, keep the layering intact.
- Don't hardcode Hyderabad's coordinates or the 8-region count anywhere
  new — both come from `app.core.config.settings` /
  `scripts/dataset_generator/road_network.py`'s parameters. If a new city
  needs different values, that's a config change, not a code change.
- Don't add lat/lon jitter or point placement anywhere without routing it
  through `app/utils/geo_utils.py::offset_latlon()` — see that file's
  docstring for why a flat epsilon is wrong (longitude degrees compress
  by `cos(latitude)`; using the same jitter for both axes introduces a
  systematic east-west drift).
