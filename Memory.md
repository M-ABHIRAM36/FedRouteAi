# Memory.md — context for AI coding tools continuing this project

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

## CURRENT STATE: ML Upgrade Complete (Phase 2)

**What changed in this build:**

- `local_model.py` — replaced Gaussian with PyTorch MLP (`MLPLocalModel`).
  Both models now inherit `BaseLocalModel` (see `app/ml/models/base_local_model.py`).
  `GaussianLocalModel` is preserved as cold-start fallback.
  `LocalModel` aliased to `MLPLocalModel` for zero-change compat with imports.
- `flower_client.py` — real gradient descent training loop with:
  - class-weighted NLLLoss (inverse-frequency weighting)
  - FedProx regularization (μ/2 * ||w_local - w_global||²)
  - ReplayBuffer per region (persists across FL rounds, retains rare events)
  - neighbor_effect labels DROPPED (not remapped) from training set
- `flower_server.py` — unchanged (AdaptiveFedAvg unchanged)
- `adaptive_aggregation.py` — unchanged (zero modifications)
- `global_model.py` — added `is_trained` flag, `predict()`, periodic disk save
- `orchestrator.py` — ML primary path + rule-based fallback:
  1. `GlobalModelStore.predict(feature_vec)` if trained
  2. `match_event()` rule-based fallback for cold start
  Graph reasoning, routing, and API contract unchanged.

**New: `app/ml/` subsystem:**
- `features/datasource.py` — FeatureSource ABC + CSVSource + DatabaseSource
- `features/windowing.py` — batch sliding-window feature extraction (10 features)
- `features/pipeline.py` — 7-stage FeaturePipeline (Load→Window→Extract→Encode→Normalize→Split→Save)
- `training/class_weights.py` — inverse-frequency weighting for XGBoost + MLP
- `training/replay_buffer.py` — ReplayBuffer + ReplayExample (rich metadata)
- `training/mlp_model.py` — EventClassifierMLP (PyTorch, 8 classes)
- `training/train_baseline_xgboost.py` — full research artifact output
- `training/evaluate_federated.py` — centralized vs federated comparison
- `models/base_local_model.py` — BaseLocalModel ABC

**EDA results (from pipeline run on 491K GPS pings):**
- 14,187 feature windows; 8 regions; 130 segments
- Normal: 98.1% | road_damage: 0.8% | construction: 0.8% | rare events: <0.1%
- Class weights critical: road_block has only 2 training windows

**17 existing tests all pass.**

**Two-command workflow to run the ML pipeline:**
```bash
cd backend
PYTHONPATH=. python app/ml/features/pipeline.py --source csv
PYTHONPATH=. python app/ml/training/train_baseline_xgboost.py
# Then run FL: python -m app.services.federated_learning.flower_server
# Then evaluate: python app/ml/training/evaluate_federated.py
```

**Read this section first if you're picking this project back up.** As
of this point, the pipeline is fully wired end-to-end (ingest → match →
persist → detect → serve, 17 passing tests, verified against a real
Postgres+PostGIS instance with 130 segments / 8 regions / 491,370 seeded
GPS pings / 3,035 historical memory rows / 23 events) — but the
"intelligence" layer is honestly rule-based, not learned:

- `event_detection/pattern_matcher.py` classifies by distance to
  hand-written target multipliers in `event_signatures.py` — this is an
  expert system, not a trained classifier.
- `federated_learning/local_model.py` (`LocalModel`) is a closed-form
  mean/std (4 numbers) per region, not a model trained by gradient
  descent. Flower's aggregation IS real (correct weighted averaging,
  real privacy properties, real per-region history) — what's federated
  is just summary statistics, not learned decision boundaries.

**Decision made**: fix this by training a real model, not by declaring
the current approach sufficient. Full reasoning below; don't re-litigate
model choice without reading it first.

### Why an MLP, not XGBoost, as the FEDERATED model
XGBoost/gradient-boosted trees are normally the right call for small
tabular feature sets like this one — but FedAvg (weighted parameter
averaging, what `AdaptiveFedAvg` implements) is defined for continuous
weight vectors. Trees aren't parameterized that way; federating them
needs fundamentally different techniques (federated boosting, histogram
aggregation) and would mean replacing the aggregation strategy, not
reusing it. A small PyTorch MLP keeps `get_parameters`/`set_parameters`'
existing contract (`local_model.py` already documents this — swap
`[mean, std]` for `[layer.weight, layer.bias, ...]`, `AdaptiveFedAvg`
doesn't change). **Train XGBoost too, but as a CENTRALIZED baseline**
(see Milestone 2) to compare the federated MLP against — that
comparison is a legitimate research result, not just an implementation
detail.

GNN is the highest-value stretch goal (directly replaces
`road_graph/neighbor_reasoning.py`'s hand-coded heuristic, and matches
DCRNN/STGCN/Graph-Enhanced-Trajectory-Anomaly-Detection from the
literature survey) — but it's Milestone 6, not Milestone 1. Don't start
there; it's harder to federate and harder to debug than the MLP path.

### The pipeline this unlocks
```
491K raw GPS pings (labeled, already seeded)
   -> batch-run signature_extractor.py over sliding windows per segment
      (the extraction LOGIC already exists — it's only ever been run
      live, on-demand, one segment at a time; this is a new batch driver
      around the same function, not new extraction logic)
Windowed feature table: (speed_ratio, density_ratio, uturn_ratio,
      variance_ratio, hour, road_type) -> label
   -> train once, centrally, as a sanity check BEFORE federating anything
Centralized XGBoost baseline -> per-class F1 (de-risks everything after:
      if features aren't separable centrally, federating won't fix that)
   -> split by region_id (already in the data)
8 regional training sets
   -> replace LocalModel's Gaussian with a PyTorch MLP, same interface
Local MLP training per region (real gradient descent, few epochs;
      college GPU server available, ~24GB VRAM, this will be fast)
   -> AdaptiveFedAvg unchanged — already does real weighted aggregation
Flower rounds -> Global MLP
   -> compare against the centralized baseline (THIS comparison is the
      research contribution: "federated MLP achieves X% of centralized
      accuracy without centralizing data")
Global model evaluation
   -> wire into orchestrator.py as the PRIMARY classifier
pattern_matcher.py: learned model first, EVENT_SIGNATURES rule-based
      fallback for cold-start segments/regions with insufficient
      training history yet — do NOT delete the rule-based matcher,
      demote it. This also gives a clean learned-vs-rule-based ablation.
```

### Milestones (in order — do not skip ahead)
1. **Batch feature-engineering script**: reuse `signature_extractor.py`
   over sliding windows across the seeded `gps_pings` table, output a
   labeled feature table (CSV/parquet). Zero new extraction logic
   needed, just a batch driver. ~1-2 days.
2. **Centralized XGBoost baseline**: per-class F1 / confusion matrix.
   Sanity-checks the features before any FL work starts. ~0.5-1 day.
3. **PyTorch MLP `LocalModel`** (same `get_parameters`/`set_parameters`
   interface) + a real training loop in `flower_client.py`'s `fit()`
   (currently calls `LocalModel.fit()` which does closed-form
   mean/std — replace with actual backprop). ~1-2 days.
4. **Full 8-region Flower run**, evaluate global MLP vs. the Milestone 2
   baseline. ~1 day (training itself is fast on the GPU server; this is
   mostly eval/debugging time).
5. **Wire the global model into `orchestrator.py`/`pattern_matcher.py`**
   as primary classifier, keep the rule-based path as fallback. ~1 day.
6. **(Stretch, highest research value) GNN** over the segment graph,
   replacing `neighbor_reasoning.py`'s heuristic. ~3-5 days.

Total to a genuinely federated, learned system: **~5-7 days**, before
the GNN stretch goal.

### Explicit non-goals (already decided, don't revisit without reason)
- No CCTV/video analytics — GPS-based architecture was deliberately
  chosen as sufficient; video stays a documented future extension
  (Phase 2 in the original project spec), not part of the core system.
- Don't remove `event_signatures.py`/`pattern_matcher.py` when the
  learned model lands — demote to fallback, not delete.

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
