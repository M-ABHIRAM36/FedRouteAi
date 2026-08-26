# FedRouteAI v2 — Current Project Technical Reference

## Document Identity

| Field | Current value |
|---|---|
| Project name | FedRouteAI |
| Current project objective | Detect road-state conditions from aggregate GPS-derived traffic behavior using a geographically partitioned federated MLP, expose live predictions on a map, and connect those predictions to a separate directed-road routing and controlled-demonstration workflow. |
| Current architecture version | Geo V2, causal 120-second feature contract, promoted `history_spatial_strong` 23-feature model |
| Documentation status | Current self-contained technical reference, derived from source, configuration, artifacts, manifests, tests, current documentation, and Git state |
| Last inspected date | 2026-08-25 |
| Current Git branch | `clg_docs1.05` |
| Current HEAD commit | `fa08bae13459a72b02f5862819c95bbaeaa7ac1b` |
| Current Git state at inspection | Dirty before this document was created: a college-report DOCX was deleted and `docs/clg_docs/backups/` was untracked. Those existing changes were not modified. |
| Current model identity | `fedrouteai-geo-v2-robust-robust-v2-hs1-prior2-unweighted-bw3-22-50r2e-seed42-r45` |
| Current model artifact | `backend/app/ml/artifacts/geo_v2/federated/robust-v2-hs1-prior2-unweighted-bw3-22-50r2e-seed42/best_model.pt` |
| Current artifact SHA-256 | `eae6665a05eb65eaf09f757f5cd6e8a22ba8ea9c9b24567c769bd77e2281aa95` |
| Current dataset identity | `geo_v2_ml_v1_fixed_contract_v2`, derived from preserved source dataset `geo_v2_ml_v1` |
| Current network identity | `osm_geo_v2` / `beeramguda-osm-20260506`; 2,968 canonical segments and 11,259 directed transitions |
| Current backend stack | Python, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL/PostGIS, PyTorch, NetworkX |
| Current frontend stack | React 19, TypeScript, Vite, React Router, TanStack Query, Axios, Leaflet/React Leaflet |

> This document describes the current implementation and is not a historical record of earlier FedRouteAI versions.

When this document conflicts with an old paper, report, diagram, README statement, or experiment, current source code and the configured current artifact win. Values that could not be verified are identified as **Not verified in current repository**.

## Executive Summary

FedRouteAI is a road-state intelligence and demonstration system built around GPS-derived traffic behavior. It addresses the practical gap between receiving moving-vehicle telemetry and presenting an interpretable road condition on a map. Its current classifier recognizes eight states: `normal`, `congestion`, `diversion`, `road_damage`, `construction`, `accident`, `flood`, and `road_block`.

The privacy motivation is that traffic observations are naturally distributed by geography. Instead of defining a system that must pool every region's raw trajectories into one training silo, the current experiment partitions training data into eight geographic clients and aggregates model updates. This is a real federated optimization experiment over regional partitions, but it is not a production deployment of independent roadside organizations. Secure aggregation, differential privacy, remote client attestation, and transport-level federation security are not implemented.

The current intelligence path is **Geo V2**. Geo V2 replaces the older 10-feature/event-signature-centered model path as the promoted runtime model. It builds a causal, ordered 23-feature vector from current traffic aggregates, cyclical time, road metadata, train-derived normal baselines, three strictly prior 120-second windows, trends, low-speed persistence, and one directed-neighbor contrast. Labels and scenario metadata are prohibited from the runtime feature vector.

The promoted model is a PyTorch MLP with a `23 -> 64 -> 32 -> 8` structure. The model was trained through eight regional clients using local gradient updates and bounded adaptive aggregation, with round 45 selected from a maximum of 50 rounds. Runtime loads the frozen checkpoint, validates its feature order, labels, scaler, and state dictionary, standardizes raw features, and fails closed with `model_unavailable` if the artifact is missing or invalid.

The road context is a canonical directed network derived from a cached OpenStreetMap Overpass response for Beeramguda. It is persisted through PostgreSQL/PostGIS as 2,968 canonical segment records and 11,259 legal directed transitions. The same network supports segment identity, directed neighbor features, map geometry, controlled vehicle movement, and coordinate-based routing. The telemetry and event schedules are synthetic; the road geometry is OSM-grounded.

The live system accepts trusted, pre-matched batches, stores append-only observations and an idempotent batch receipt, updates a current-state projection, runs Geo V2 inference, persists predictions, and exposes normalized snapshots. The React/Leaflet Traffic Map polls those snapshots and renders separate network, telemetry, vehicle, prediction, event, and route layers. Vehicle interpolation in the browser is visual only and does not create new telemetry.

Road-state prediction and route calculation are separate subsystems. The current map route uses coordinate snapping and Dijkstra over persisted directed topology, with **distance** as the default cost. Predictions are inspected after route selection. The user can explicitly request another route by excluding currently abnormal predicted segments, but the default route is not prediction-weighted or continuously traffic-aware.

The controlled demonstration lets a user calculate a route, require at least 1.5 km of route distance, select `normal`, `congestion`, or `accident`, and run deterministic vehicles over the selected corridor. The simulator knows the scripted scenario in order to alter traffic behavior, but scenario labels and event IDs are removed before model inference. This validates integration and behavior under controlled synthetic conditions; it is not independent real-world incident validation.

## 1. Problem Definition

### 1.1 What FedRouteAI Solves

Centralized traffic systems commonly collect raw location histories into a single service. That creates privacy and governance risks, especially when trajectories can identify routines or individuals. Traffic is also geographically non-IID: road capacity, traffic volume, road type, event frequency, and class balance differ strongly by region. A model trained as if all regions have the same distribution can underrepresent small or unusual regions.

Road state changes over time. A low speed alone is ambiguous: it can mean congestion, a junction, normal local behavior, an accident, construction, flooding, or a blocked road. Current observations need both historical context and spatial context. FedRouteAI therefore compares current segment behavior with normal prehistory, prior causal windows, trends, persistence, and directed neighboring segments.

The application also needs a live operational path, not only an offline score. FedRouteAI connects incoming observations to persistent current state, inference, API snapshots, and a dynamic map. It then connects the map to routing and a controlled demonstration so evaluators can observe the complete flow.

### 1.2 Two Separate Subsystems

**ROAD CONDITION DETECTION**

```text
telemetry -> segment aggregate -> causal Geo V2 features -> frozen MLP
          -> predicted road-state class -> prediction persistence -> map layer
```

**ROUTE CALCULATION**

```text
origin/destination -> coordinate snapping -> directed OSM topology
                   -> shortest-distance path -> geometry/distance/duration
                   -> post-route prediction inspection
```

Detection estimates a class for a road segment. Routing calculates a legal path. The current coordinate route does not automatically convert prediction confidence or traffic density into edge cost.

## 2. Current System in One Diagram

```text
FedRouteAI v2
|
+-- OFFLINE / DATA AND TRAINING
|   |
|   +-- Cached OSM Overpass response: Beeramguda
|   |   +-- normalize drivable ways and source geometry
|   |   +-- deterministic canonical segment IDs
|   |   +-- preserve direction, metadata, LineString geometry
|   |   `-- derive 11,259 legal directed transitions
|   |
|   +-- OSM-grounded synthetic traffic generation
|   |   +-- 1,000 persistent simulated vehicles
|   |   +-- normal prehistory and scripted event episodes
|   |   +-- labels retained separately as training ground truth
|   |   `-- eight geographic partitions: REGION_01..REGION_08
|   |
|   +-- Causal feature construction
|   |   +-- current aggregate traffic state
|   |   +-- time and road metadata
|   |   +-- train-normal prehistory baselines
|   |   +-- t-1/t-2/t-3 shifted windows at 120-second cadence
|   |   +-- trends and low-speed persistence
|   |   `-- directed-neighbor speed delta
|   |
|   +-- Eight logical federated clients
|   |   +-- client-local regional rows
|   |   +-- local AdamW optimization, 2 epochs/round
|   |   +-- no geographic row movement
|   |   `-- model updates and client metrics
|   |
|   +-- Adaptive federated aggregation
|   |   +-- bounded normalized client weights (3%-22%)
|   |   +-- global MLP distribution for next round
|   |   `-- up to 50 rounds; selected round 45
|   |
|   +-- Model validation and selection
|   |   +-- deployment validation macro F1 primary criterion
|   |   +-- false-positive/anomaly-recall/event-balanced gates
|   |   +-- untouched test used after selection
|   |   `-- final test receipt and artifact hashes
|   |
|   `-- Frozen promoted artifact
|       +-- exact 23-feature order
|       +-- train-fit scaler
|       +-- 23 -> 64 -> 32 -> 8 model state
|       +-- eight-class label mapping
|       `-- dataset/network/model provenance
|
`-- ONLINE / RUNTIME
    |
    +-- Trusted live telemetry OR controlled Geo V2 simulator
    |   +-- source_id / run_id / batch_id / tick_number
    |   +-- pre-matched segment IDs and positions
    |   +-- controlled scenario labels scrubbed before inference
    |   `-- authenticated live-batch API when externally posted
    |
    +-- Live ingestion
    |   +-- Pydantic validation and maximum batch size
    |   +-- SHA-256 payload identity and duplicate handling
    |   +-- append-only GPS observations
    |   `-- per-segment current-state projection
    |
    +-- Traffic aggregation and context
    |   +-- speed, speed variance, vehicle count, occupancy, flow
    |   +-- stopped fraction
    |   +-- canonical normal baseline
    |   +-- durable + process-local causal prior windows
    |   `-- same-tick directed outgoing-neighbor context
    |
    +-- Geo V2 inference
    |   +-- construct raw exact 23-feature vector
    |   +-- verify current artifact contract
    |   +-- standardize using frozen train scaler
    |   +-- frozen MLP probabilities
    |   `-- class, confidence, model version, trace
    |
    +-- Persistence and API
    |   +-- SegmentPrediction rows
    |   +-- latest prediction/current state/live batch queries
    |   `-- GET /api/v1/live-map/snapshot
    |
    +-- React/Leaflet Traffic Map
    |   +-- network, telemetry, prediction, vehicle, event layers
    |   +-- region/layer controls and freshness state
    |   +-- selected-segment history and prediction changes
    |   `-- route selection and controlled demo controls
    |
    `-- Separate routing branch
        +-- user origin/destination coordinates
        +-- snap to canonical LineStrings
        +-- Dijkstra over directed transitions
        +-- distance-cost ordered segment path
        +-- geometry, distance, speed-limit duration
        +-- post-route prediction inspection
        `-- optional explicit abnormal-segment exclusion reroute
```

## 3. Current Project Directory Tree

The tree is intentionally selective. Generated caches, `.git`, `.venv`, `node_modules`, `dist`, `build`, and `__pycache__` are excluded.

```text
fedrouteai/
|-- README.md                              [REFERENCE; partly stale]
|-- HOW_TO_RUN_PROJECT.md                  [CURRENT runbook]
|-- CLAUDE.md                              [REFERENCE; mixed current/historical]
|-- about_project.md                       [HISTORICAL project tour]
|-- about_project_v2.md                    [CURRENT reference]
|-- run_project.py                         [CURRENT launcher]
|-- provenance_audit.txt                   [REFERENCE provenance audit]
|-- backend/                               [CURRENT]
|   |-- requirements.txt
|   |-- alembic.ini
|   |-- alembic/versions/
|   |-- app/
|   |   |-- main.py
|   |   |-- api/
|   |   |   |-- dependencies/
|   |   |   `-- v1/endpoints/
|   |   |-- core/{config,constants,logging_config}.py
|   |   |-- db/{base,session,init_db}.py
|   |   |-- models/
|   |   |-- schemas/
|   |   |-- repositories/
|   |   |-- services/
|   |   |   |-- event_detection/
|   |   |   |-- federated_learning/        [LEGACY/V1 retained path]
|   |   |   |-- geo_v2/                    [CURRENT runtime]
|   |   |   |-- historical_memory/
|   |   |   |-- live_ingestion/
|   |   |   |-- live_map/
|   |   |   |-- live_simulation/
|   |   |   |-- map_matching/
|   |   |   |-- road_graph/
|   |   |   `-- routing/
|   |   |-- ml/
|   |   |   |-- geo_v2/                    [CURRENT feature/model/training code]
|   |   |   |-- artifacts/geo_v2/          [CURRENT + alternate artifacts]
|   |   |   |-- features/                  [EARLIER 10-feature subsystem]
|   |   |   |-- models/
|   |   |   `-- training/
|   |   `-- utils/
|   `-- tests/                              [CURRENT; 24 test modules]
|-- frontend/                              [CURRENT]
|   |-- package.json
|   |-- vite.config.ts
|   `-- src/
|       |-- App.tsx
|       |-- pages/{Dashboard,TrafficMap,Prediction,Federated,Training,Analysis,Results,About}/
|       |-- components/{map,prediction,layout,cards,charts,common}/
|       `-- services/{api,parsers}/
|-- federated_clients/                     [EARLIER Flower client runner retained]
|   |-- run_client.py
|   `-- region_config/region_01.yaml...region_08.yaml
|-- scripts/
|   |-- geo_v2/                            [CURRENT dataset/network/training/demo tools]
|   |-- dataset_generator/                 [V1 synthetic dataset tools]
|   |-- seed_db.py
|   `-- verify_live_ingestion.py
|-- data/
|   |-- geo_v2/                            [CURRENT OSM cache and Geo V2 datasets]
|   |-- raw/fedrouteai_dataset/             [V1 dataset retained]
|   |-- calibration/                       [EXPERIMENTAL]
|   `-- processed/
|-- results/                               [HISTORICAL/EXPERIMENTAL FL results]
`-- docs/
    |-- architecture.md                    [REFERENCE; V1 sections stale]
    |-- data_models.md
    |-- api_contract.md
    |-- routing_v1.md                      [CURRENT route boundary]
    |-- clg_docs/                          [CURRENT college documentation line]
    |   |-- figures/{svg,png,pdf}/
    |   `-- report/
    |-- docs1.01/                          [HISTORICAL IEEE/reference material]
    |-- doc1.00/                           [HISTORICAL paper source]
    |-- paper/                             [RESEARCH build material]
    `-- paper-diagrams all/                [EXPERIMENTAL diagram material]
```

## 4. System Component Tree

```text
FedRouteAI
|-- Data Layer
|   |-- cached Beeramguda OSM response
|   |-- canonical segment/transition network
|   |-- Geo V2 raw synthetic telemetry and separate ground truth
|   |-- causal feature tables and train-fit scalers
|   `-- regional partitions REGION_01..REGION_08
|-- Federated Learning
|   |-- eight regional clients
|   |-- local GeoV2EventClassifierMLP training
|   |-- bounded adaptive aggregation
|   |-- round history, selection gates, checkpoints
|   `-- promoted round-45 frozen artifact
|-- ML / Geo V2
|   |-- CausalFeatureBuilder / build_feature_trace
|   |-- 23-feature history_spatial_strong contract
|   |-- GeoV2MLP and GeoV2ModelStore
|   `-- GeoV2PredictionService / runtime inference cache
|-- Backend
|   |-- FastAPI v1 endpoints
|   |-- services
|   |-- repositories
|   |-- SQLAlchemy models and Pydantic schemas
|   `-- startup graph cache
|-- Network
|   |-- OSM normalization
|   |-- PostGIS LineStrings
|   |-- directed transitions
|   `-- versioned route graph cache
|-- Database
|   |-- network and regions
|   |-- GPS/live batches/current state
|   |-- historical memory
|   |-- scenarios/predictions/events
|   `-- FL round records
|-- Frontend
|   |-- React application shell
|   |-- TanStack Query + Axios API state
|   |-- Leaflet Traffic Map
|   `-- training/results/reference pages
|-- Routing
|   |-- coordinate snapping
|   |-- directed Dijkstra distance path
|   |-- route geometry and free-flow duration
|   `-- prediction summary / explicit exclusions
|-- Live Ingestion
|   |-- X-Live-Ingest-Key
|   |-- idempotent trusted batches
|   |-- append-only observations
|   `-- current-state projection and snapshot
`-- Controlled Demonstration
    |-- in-process run registry
    |-- normal/congestion/accident scenarios
    |-- 250/1000 vehicle modes
    |-- selected-route corridor
    |-- label scrubbing before inference
    `-- deterministic tick-step map updates
```

## 5. Complete Data Flow

### 5.1 Training and Deployment

```text
OSM-grounded synthetic regional traffic
    -> preserve scenario truth separately
    -> aggregate by segment and 120-second tick
    -> build normal-prehistory baselines from train data
    -> construct causal current/history/spatial features
    -> reject label/event/scenario/ground-truth identity columns
    -> split into REGION_01 ... REGION_08 clients
    -> distribute current global MLP to each client
    -> local AdamW training on regional rows
    -> return parameters + client metrics, not raw trajectories
    -> bounded adaptive aggregation
    -> next global model
    -> validation gates and round selection
    -> one-time untouched test evaluation
    -> freeze state + scaler + labels + feature/network metadata
    -> configure best_model.pt for runtime
```

The experiment is geographically federated in its data partition and model-update semantics. It is orchestrated within the repository's offline training environment; independent production organizations and secure federation infrastructure are not verified.

### 5.2 Runtime Prediction

```text
live or controlled vehicle observations
    -> trusted batch validation / idempotency
    -> append-only GPSPing rows
    -> SegmentCurrentState aggregate
    -> canonical baseline + prior prediction traces
    -> directed outgoing-neighbor same-tick observations
    -> exact raw 23-feature vector
    -> frozen train scaler
    -> frozen Geo V2 MLP
    -> 8 class probabilities
    -> predicted label + confidence + model version
    -> SegmentPrediction persistence
    -> live-map snapshot
    -> React/Leaflet Traffic Map
```

### 5.3 Routing

```text
origin and destination map clicks
    -> POST /api/v1/routes/shortest
    -> validate selected network source/version
    -> project coordinates onto nearest persisted LineStrings
    -> enforce maximum snap distance
    -> load cached directed segment graph
    -> optionally remove explicit avoid_segment_ids
    -> Dijkstra with segment distance weights
    -> ordered segment IDs
    -> trimmed/assembled route geometry
    -> total distance
    -> speed-limit-derived estimated duration
    -> inspect latest predictions for route segments
    -> return route + prediction coverage/warnings
    -> optional user-requested exclusion reroute
    -> optional controlled route demonstration
```

## 6. Dataset Architecture

### 6.1 Current Dataset Identity

| Property | Verified value |
|---|---|
| Preserved source dataset | `data/geo_v2/fedrouteai_dataset_geo_v2_ml_v1/` |
| Current fixed-contract dataset | `data/geo_v2/fedrouteai_dataset_geo_v2_ml_v1_fixed_contract_v2/` |
| Dataset version | `geo_v2_ml_v1_fixed_contract_v2` |
| Source dataset version | `geo_v2_ml_v1` |
| Network | `beeramguda-osm-20260506` |
| Geographic clients | 8 (`REGION_01` through `REGION_08`) |
| Canonical network segments represented | 2,968 |
| Source simulation vehicles | 1,000 persistent IDs |
| Cadence | 120 seconds for current ML contract |
| Feature rows per train/validation/test split | 332,416 |
| Normal rows per split | 331,632 |
| Anomaly rows per split | 784, 112 for each of seven non-normal classes |
| Ground truth | Separate scripted scenario/episode data joined after label-free feature construction |
| Data character | OSM-grounded synthetic telemetry, not real GPS observations |

The source manifest records all eight regions and temporal train, validation, and test splits. The fixed-contract manifest records train/validation derivation from canonical train-normal prehistory. A test CSV now exists because the finalization workflow materialized it after model selection; the manifest still says `test_derived: false`, so that field is stale. `final_test_receipt.json` binds the final test file by SHA-256.

### 6.2 Training Labels Versus Runtime Features

**TRAINING LABELS** are the separate class targets used to calculate loss and evaluation metrics. They originate from controlled synthetic episode schedules.

**RUNTIME FEATURES** are traffic aggregates, time, road properties, historical values, and neighbor contrast. Runtime inference does not receive a label, scenario name, ground-truth event, event ID, vehicle ID, or device ID.

`backend/app/ml/geo_v2/features.py` explicitly rejects feature columns containing tokens such as `label`, `event`, `scenario`, `ground_truth`, `vehicle_id`, `device_id`, `severity`, `active_event`, or `target`. Feature construction has no target argument. The controlled demo additionally replaces observation labels with `normal` and event IDs with an empty string before inference items are built.

This separation prevents direct target leakage. It does not make synthetic scenarios equivalent to real unknown incidents: scenario physics still changes speed, density, variance, availability, and movement, which is the intended observable signal.

## 7. Road Network Architecture

### 7.1 Identity and Counts

| Property | Current value |
|---|---|
| Source | Cached OpenStreetMap Overpass response, ODbL |
| Query area | Beeramguda bounding box recorded in `data/geo_v2/README.md` |
| OSM base timestamp | `2026-06-01T08:52:28Z` |
| Network source | `osm_geo_v2` |
| Network version | `beeramguda-osm-20260506` |
| Canonical segments | 2,968 |
| Directed transitions | 11,259 |
| Accepted distinct OSM way IDs | 1,301 |
| Regions | 8 |
| One-way canonical segments | 150 |
| Geometry | PostGIS `LINESTRING`, SRID 4326 |

The cache is geographically real OSM geometry; generated vehicle observations and incidents are synthetic. OSM is the network source, not the ML training dataset.

Canonical segment IDs are deterministic BLAKE2s-derived identifiers from `osm_way_id:start_node_id:end_node_id`. Metadata includes OSM way and endpoint node IDs, highway type, geometry, one-way direction, length, lanes, speed limit, bridge/tunnel/junction fields, region, and import identity. Legal transitions connect a source segment's directed exit node to a target segment's directed entry node; self-transitions are excluded.

### 7.2 Network Uses

1. **Segment association:** incoming trusted Geo V2 observations refer to canonical segment IDs; the older `/ingest/gps` path additionally performs geometric map matching against legacy segments.
2. **Spatial features:** the feature builder uses persisted directed outgoing transitions to obtain same-tick neighbor context.
3. **Map rendering:** the frontend requests canonical segment geometry and draws the network as Leaflet polylines.
4. **Routing:** the route graph treats canonical road segments as nodes and legal transitions as directed edges.

The database currently contains 3,098 total rows in `segments`: 2,968 current Geo V2 segments plus 130 retained legacy network rows. The correct current Geo V2 network count is 2,968, not 3,098.

## 8. Geo V2 Feature Architecture

### 8.1 Purpose and Version Boundary

Geo V2 exists because a current speed/density snapshot is insufficient to distinguish temporary road states reliably. It adds causal historical context, stable road metadata, and directed network context. It also formalizes one identical ordered contract across dataset derivation, artifact metadata, scaling, and runtime inference.

The current deployed variant is `history_spatial_strong`, feature version `geo-v2-history_spatial_strong-23-v2`. Earlier repository paths contain a 10-feature MLP and a full 27-feature Geo V2 candidate. Neither is the configured promoted runtime artifact.

### 8.2 Exact Ordered 23-Feature Contract

| # | Feature | Group | Meaning |
|---:|---|---|---|
| 1 | `avg_speed_kmph` | Current traffic | Mean segment speed in the current aggregate window |
| 2 | `speed_std_kmph` | Current traffic | Current speed dispersion |
| 3 | `vehicle_count` | Current traffic | Current unique/aggregate vehicle count |
| 4 | `occupancy` | Current traffic | Current estimated occupancy |
| 5 | `flow_rate_vph` | Current traffic | Current vehicles-per-hour flow estimate |
| 6 | `stopped_fraction` | Current traffic | Fraction of current vehicles considered stopped |
| 7 | `hour_sin` | Temporal | Sine encoding of fractional hour |
| 8 | `hour_cos` | Temporal | Cosine encoding of fractional hour |
| 9 | `road_type_code` | Road metadata | Ordinal road type: residential 0, collector 1, arterial 2, highway link 3 |
| 10 | `lane_count` | Road metadata | Persisted lane count |
| 11 | `max_speed_kmph` | Road metadata | Persisted maximum speed |
| 12 | `baseline_speed_kmph` | Historical memory | Train-normal prehistory mean speed |
| 13 | `baseline_speed_std_kmph` | Historical memory | Train-normal prehistory speed standard deviation |
| 14 | `baseline_vehicle_count` | Historical memory | Train-normal prehistory mean vehicle count |
| 15 | `speed_to_baseline` | Baseline deviation | Current mean speed divided by baseline speed, denominator floored at 1.0 |
| 16 | `count_to_baseline` | Baseline deviation | Current count divided by baseline count, denominator floored at 0.5 |
| 17 | `std_to_baseline` | Baseline deviation | Current speed std divided by baseline std, denominator floored at 0.5 |
| 18 | `prior_speed_mean_3` | Prior windows | Mean speed across the three prior cadence slots |
| 19 | `prior_count_mean_3` | Prior windows | Mean count across the three prior cadence slots |
| 20 | `speed_trend` | Trend | Current speed minus prior three-slot mean speed |
| 21 | `count_trend` | Trend | Current count minus prior three-slot mean count |
| 22 | `low_speed_persistence_3` | Persistence | Fraction of prior slots below 70% of baseline speed |
| 23 | `neighbor_speed_delta` | Directed spatial context | Current speed minus mean speed of observed directed outgoing neighbors |

The selected 23-feature model does **not** consume `neighbor_speed_mean`, `neighbor_vehicle_count_mean`, `neighbor_occupancy_mean`, or `observed_neighbor_count`, although the general feature builder computes them for the full 27-feature variant. `_timestamp` and `history_observed_slots` are trace/bookkeeping fields, not model inputs.

### 8.3 Feature Architecture

```text
CURRENT TRAFFIC
  avg speed, speed std, count, occupancy, flow, stopped fraction

TEMPORAL FEATURES
  hour_sin, hour_cos

ROAD METADATA
  road type code, lanes, maximum speed

HISTORICAL MEMORY
  baseline speed, baseline speed std, baseline vehicle count

BASELINE DEVIATIONS
  speed ratio, count ratio, std ratio

PRIOR WINDOWS
  prior three-slot speed mean, prior three-slot count mean

TRENDS
  speed trend, count trend

LOW-SPEED PERSISTENCE
  fraction of t-1/t-2/t-3 below 0.7 * baseline speed

DIRECTED NEIGHBOR CONTEXT
  current speed - same-tick outgoing-neighbor mean speed
                         |
                         v
              EXACT 23-FEATURE VECTOR
                         |
                         v
                MODEL INPUT CONTRACT
                         |
                         v
                    Geo V2 MLP
                         |
                         v
                  ROAD-STATE OUTPUT
```

Runtime sends raw values in this exact order. `GeoV2ModelStore` applies the frozen train scaler as `(value - mean) / scale`, reconstructs the MLP, and validates the labels and state dictionary before returning probabilities.

## 9. Historical Memory and Causality

Normal prehistory establishes what is typical for each segment rather than imposing one city-wide normal. Current values are compared with baseline speed, speed variability, and vehicle count. Prior windows add short-term direction: whether a state is improving, deteriorating, or persisting.

The current contract requires exact 120-second cadence. At timestamp `t`, prior values are read only from `t-120s`, `t-240s`, and `t-360s`. Missing slots use the fixed segment baseline. Offline rolling features call `shift(1)` before the rolling mean. Runtime only accepts historical rows with timestamps strictly earlier than the inference timestamp and combines durable prediction traces with a small process-local cache.

```text
past                                                     inference
 |                                                           |
 +-- normal prehistory --------+------------------------------+
                               |
                       t-360s  t-240s  t-120s       t
                         |       |       |           |
                         +-------+-------+           |
                            prior mean               |
                            persistence              |
                            trend = current - prior -+

Allowed at t: fixed train-normal baseline, t-360, t-240, t-120,
              current t, and same-tick directed neighbors.
Forbidden at t: t+120 or later observations, future scenario outcomes,
                current/future labels, event IDs, or ground truth.
```

Historical context matters because identical current speeds can mean different things on roads with different normal speeds or after different trajectories. The fixed baseline and shifted windows reduce this ambiguity while preventing future leakage.

## 10. Machine Learning Model

### 10.1 Current Promoted Artifact

| Property | Verified value |
|---|---|
| Family | PyTorch multilayer perceptron |
| Input dimension | 23 |
| Hidden layers | 64, then 32 |
| Output dimension | 8 |
| Architecture | Linear -> BatchNorm -> ReLU -> Dropout(0.2) -> Linear -> BatchNorm -> ReLU -> Linear -> LogSoftmax |
| Trainable parameters | 4,072 |
| Runtime device | CPU by current model-store load path |
| Normalization | Frozen train-fit standardization stored with artifact |
| Artifact path | `backend/app/ml/artifacts/geo_v2/federated/robust-v2-hs1-prior2-unweighted-bw3-22-50r2e-seed42/best_model.pt` |
| Model version | `fedrouteai-geo-v2-robust-robust-v2-hs1-prior2-unweighted-bw3-22-50r2e-seed42-r45` |
| Feature version | `geo-v2-history_spatial_strong-23-v2` |
| Network version | `beeramguda-osm-20260506` |
| Selected round | 45 |

Model shape:

```text
23 raw ordered values
    -> frozen standard scaler
    -> Linear(23, 64)
    -> BatchNorm1d(64)
    -> ReLU
    -> Dropout(0.2)
    -> Linear(64, 32)
    -> BatchNorm1d(32)
    -> ReLU
    -> Linear(32, 8)
    -> LogSoftmax
    -> probability distribution over eight classes
```

### 10.2 Ordered Output Mapping

| Index | Class |
|---:|---|
| 0 | `normal` |
| 1 | `congestion` |
| 2 | `diversion` |
| 3 | `road_damage` |
| 4 | `construction` |
| 5 | `accident` |
| 6 | `flood` |
| 7 | `road_block` |

### 10.3 Training Configuration

The selected run uses seed 42, AdamW, learning rate `0.001`, weight decay `0.0001`, batch size 256, unweighted NLL, 50 maximum rounds, two local epochs per round, minimum 12 rounds, and early-stopping patience 6. Regional normal rows were sampled toward a 2% local anomaly fraction without duplicating event rows or moving rows between regions.

The current artifact's full held-out test records accuracy `0.9952439112` and macro F1 `0.3200260364`. Accuracy is dominated by extreme class imbalance and must not be used alone. Anomaly recall is `0.3443877551`, anomaly precision `0.2093023256`, normal false-positive rate `0.0030756984`, diversion recall is zero, and construction recall is approximately `0.1071`. The artifact report explicitly rejects unattended safety-critical use.

## 11. Federated Learning

### 11.1 Current Training Topology

```text
CLIENT DATA                              MODEL UPDATE

REGION_01 local rows -- local MLP train -- parameters + metrics --+
REGION_02 local rows -- local MLP train -- parameters + metrics --|
REGION_03 local rows -- local MLP train -- parameters + metrics --|
REGION_04 local rows -- local MLP train -- parameters + metrics --+-->
REGION_05 local rows -- local MLP train -- parameters + metrics --|   ADAPTIVE
REGION_06 local rows -- local MLP train -- parameters + metrics --| AGGREGATION
REGION_07 local rows -- local MLP train -- parameters + metrics --|     |
REGION_08 local rows -- local MLP train -- parameters + metrics --+     v
                                                               GLOBAL MODEL
                                                                    |
                             next round distribution <--------------+
```

The current promoted training uses eight geographic clients and adaptive bounded client weights. The configuration includes quality/rarity/history gate factors and a minimum/maximum normalized contribution of 3%/22%. Training selected round 45 from at most 50 rounds and preserved round histories, client distributions, weights, validation selection, provenance, and final test receipt.

Raw regional rows are not model updates. The federation boundary is designed around local rows and shared parameters/metrics. However, the current evidence is a controlled offline/simulated federation in one research environment, not eight independently administered machines. The repository also retains an older Flower server/client path and `federated_clients/` launchers; those are not the source of the promoted Geo V2 artifact.

No claim is made for differential privacy, secure aggregation, encrypted model-update protocols, poisoning resistance, trusted execution, or formal privacy guarantees. Those mechanisms are not implemented in the current promoted workflow.

## 12. Live Ingestion

### 12.1 Trusted Batch API

`POST /api/v1/ingest/live/batch` accepts trusted pre-matched multi-vehicle observations. External callers authenticate with `X-Live-Ingest-Key`. If `LIVE_INGEST_API_KEY` is unset, this endpoint returns 503; a mismatched key returns 401. Other read/control APIs are not generally authenticated.

Each batch has `source_id`, `run_id`, `batch_id`, `tick_number`, observations, and optional network identity. Input validation enforces IDs, timestamps, known segments, segment-region consistency, unique observation IDs within a batch, and a configurable default maximum of 2,000 observations.

Idempotency uses `(source_id, run_id, batch_id)` plus a SHA-256 hash of the canonical payload:

- Same identity and same payload: accepted as a duplicate without new observation rows.
- Same identity and changed payload: conflict.
- Per-observation uniqueness: `(ingestion_batch_id, observation_id)`.

The service stores a batch receipt and append-only `GPSPing` rows, then updates `SegmentCurrentState` with latest timestamp, count, average speed, density, current event, availability, and last update. `source_id` and `run_id` keep concurrent or historical demo/live sessions separated.

### 12.2 One Batch to the Map

```text
incoming trusted batch
    -> API-key check
    -> Pydantic validation
    -> payload hash / duplicate lookup
    -> segment and region validation
    -> transactional batch + ping persistence
    -> current segment-state upsert
    -> Geo V2 aggregate/context construction
    -> frozen-model inference
    -> prediction upsert
    -> GET /live-map/snapshot query
    -> frontend poll and layer update
```

Snapshot freshness uses the latest batch and a server freshness window based on three configured tick intervals, with a minimum of ten seconds. The frontend separately classifies its receipt state as connecting, live, delayed, stale, paused, or offline.

The older `POST /api/v1/ingest/gps` path is different: it accepts one device trajectory, geometrically map-matches pings, persists matched rows, and schedules legacy event detection through in-process FastAPI `BackgroundTasks`. It has no live-batch idempotency and is not the primary Geo V2 controlled-demo path.

## 13. Live Vehicle Simulation

The current route-bound controlled demo uses `GeoV2Simulation` and `GeoV2DemoRuntime`. The frontend offers 250 and 1,000 vehicle modes. Ninety percent of controlled-demo vehicles are configured to follow the selected corridor where legal transitions permit; other vehicles retain ordinary simulated movement.

Movement follows canonical OSM LineString geometry and legal directed transitions. Position is interpolated along geometry by the simulator. At transitions, route-following, road availability, one-way constraints, and legal outgoing transitions are applied. A blocked/unavailable next segment can cause fallback to another legal transition.

Each backend demo step advances 120 simulated seconds. Frontend controls request frequency at approximately four seconds for 1x, two seconds for 2x, and at least 1.2 seconds for 5x. The browser then visually interpolates markers between authoritative snapshots with cubic ease-out; these intermediate pixels are not stored GPS pings.

Supported frontend scenarios are:

- `normal`: no scheduled disturbance.
- `congestion`: controlled congestion on a midpoint corridor group.
- `accident`: a controlled accident on a midpoint corridor segment.

The frontend always sends random seed 42, so equivalent starts are deterministic subject to the same model, network, and database state. The in-process demo registry permits up to eight active runs and expires them after one hour; runs do not survive backend restart.

> Scenario behavior is NOT ground truth supplied to the model.

The simulator internally knows the scenario to change physical traffic behavior. Before inference, `scrub_demo_observations()` replaces labels with `normal` and event IDs with empty values. The model receives only aggregate traffic, historical, road, temporal, and neighbor features. Scenario ground truth remains available as a separate map/evaluation layer.

## 14. Road-State Prediction

```text
telemetry
  -> per-segment aggregate
  -> canonical baseline + causal history + neighbor context
  -> exact ordered raw 23 features
  -> frozen standardization
  -> frozen MLP probabilities
  -> maximum-probability predicted class
  -> confidence and model metadata
  -> SegmentPrediction row
  -> live snapshot
  -> prediction layer and segment details on map
```

The output classes are `normal`, `congestion`, `diversion`, `road_damage`, `construction`, `accident`, `flood`, and `road_block`.

A **model prediction** is the MLP output. **Scenario truth** is the simulator's separate scripted event description. A **telemetry label** is a field accepted by the trusted ingestion schema and used in current-state/event projections; in the controlled Geo V2 inference path it is scrubbed to normal and is not a model input. These concepts must not be merged.

## 15. Traffic Map

The current operational map is `frontend/src/pages/TrafficMap/index.tsx`. It uses React Leaflet and TanStack Query. Static segment geometry is cached indefinitely; dynamic snapshots are polled. There is no WebSocket or server-sent-event transport.

Map layers:

- **Network layer:** canonical road geometry.
- **Telemetry layer:** style derived from current speed ratio, occupancy, density, and availability; this is not model output.
- **Prediction layer:** style derived from `predicted_event` and confidence.
- **Vehicle layer:** latest vehicle positions with visual interpolation.
- **Event layer:** telemetry/scenario event markers, with scenario ground truth explicitly identified.
- **Route layer:** backend-returned ordered route geometry and snapped endpoints.

The page supports client-side region filtering and layer toggles. Region filtering does not reduce the backend snapshot payload. It shows vehicles, active segments, predicted events, average speed, tick/time, and freshness. Segment inspection shows prediction, confidence, model version, telemetry, historical baseline, deviation trace, trend, and neighbor delta.

Prediction history on the map is session-local: six entries for the selected segment and eight recent prediction changes. It is not the complete database historical memory. In demo mode, at most 250 markers are rendered even when 1,000 vehicles are active; the backend still simulates and reports the larger count.

Several older frontend pages read static training/result artifacts. The Dashboard's traffic preview remains a placeholder; the actual current map is the `/map` page. Some older API clients hardcode `http://localhost:8000` instead of honoring `VITE_API_BASE_URL`.

## 16. Routing System

### 16.1 Current Coordinate Route

The Traffic Map calls `POST /api/v1/routes/shortest`. The user selects origin and destination map coordinates. The backend projects each point onto the nearest persisted canonical LineString and rejects a point if it is farther than the configured maximum snap distance, default 250 m.

The graph represents road segments as nodes and legal transitions as directed edges. Edge weight is segment length. NetworkX Dijkstra returns one ordered path. The service trims the first and last geometries at snapped fractions, assembles the full route geometry, sums distance, and calculates an estimated duration from segment speed limits.

**Current default route cost is distance-only.** The returned `cost_basis` is `distance`, or `distance with explicit segment exclusions` when exclusions were provided. Estimated duration is a post-selection free-flow estimate and is not the optimized cost.

After path calculation, the service queries latest predictions for the requested `source_id`/`run_id`, reports coverage, counts abnormal segments, and adds warnings. These predictions do not alter the initial route cost.

The frontend can offer **Find alternative** when current route segments have non-normal predictions. That action submits those IDs as explicit exclusions and recalculates a distance route with those segment nodes removed. This is user-triggered prediction-informed avoidance, not automatic traffic-aware edge weighting.

### 16.2 Current Versus Future Routing

| Capability | Current routing | Future traffic-aware routing |
|---|---|---|
| Topology | Directed persisted OSM transitions | Same or improved topology |
| Default cost | Distance | Live/predicted travel time or calibrated risk |
| Predictions | Inspected after path selection | Incorporated into cost or constraints |
| Rerouting | Explicit user action with segment exclusions | Automatic policy-driven recalculation |
| ETA | Speed-limit-derived free-flow duration | Live calibrated ETA |
| Alternatives | One route per request | Ranked alternatives may be added |

The backend retains an older `POST /api/v1/routes` endpoint that applies penalties to legacy detected-event segments and optimizes travel-time weights. The current Traffic Map does not call that endpoint. It must not be used to claim that the current coordinate route is traffic-aware.

## 17. Route-Bound Demonstration

```text
user selects origin and destination
    -> calculate current directed shortest-distance route
    -> require route distance >= 1.5 km
    -> retain ordered route segment IDs
    -> choose NORMAL, CONGESTION, or ACCIDENT
    -> choose 250 or 1000 vehicles
    -> create deterministic demo run, seed 42
    -> controlled vehicles follow legal route corridor transitions
    -> simulator modifies traffic physics for selected scenario
    -> remove scenario label/event ID from inference observations
    -> persist telemetry/current state
    -> construct Geo V2 features and infer
    -> persist predictions
    -> poll snapshot
    -> update prediction/telemetry/vehicle/event/route layers
```

The route is a real output of the routing subsystem and a movement corridor for the simulator. The selected scenario is demonstration control, not a class supplied to the MLP. The demonstration proves orchestration and visual behavior under controlled conditions; it does not establish real-world detection accuracy.

## 18. Backend Architecture

```text
backend/app/
|-- main.py
|-- api/
|   |-- dependencies/geo_v2_demo.py
|   `-- v1/
|       |-- router.py
|       `-- endpoints/
|           |-- health.py
|           |-- ingest.py
|           |-- live_ingest.py
|           |-- live_map.py
|           |-- live_scenarios.py
|           |-- geo_v2_demo.py
|           |-- segments.py
|           |-- routes.py
|           |-- events.py
|           |-- prediction.py
|           |-- predict.py
|           |-- federated.py
|           `-- metrics.py
|-- core/{config,constants,logging_config}.py
|-- db/{base,session,init_db}.py
|-- models/
|-- schemas/
|-- repositories/
|-- services/
|   |-- geo_v2/
|   |-- live_ingestion/
|   |-- live_map/
|   |-- live_simulation/
|   |-- routing/
|   |-- road_graph/
|   |-- historical_memory/
|   |-- map_matching/
|   |-- event_detection/
|   `-- federated_learning/
|-- ml/
|   |-- geo_v2/
|   |-- artifacts/
|   |-- features/
|   |-- models/
|   `-- training/
`-- utils/
```

The intended dependency direction is:

```text
API endpoint -> service -> repository -> SQLAlchemy model
Pydantic schemas remain separate API contracts.
```

Geo V2 inference, live ingestion, live map, and shortest-route paths substantially follow this structure. Some retained endpoints (`metrics.py`, legacy `predict.py`, and parts of old routing/segment APIs) directly query models or contain business logic; those are current layering inconsistencies, not the architecture to copy for new work.

Major current services include `GeoV2PredictionService`, `GeoV2DemoRuntime`, `GeoV2Simulation`, `LiveIngestionService`, the live-map snapshot service, `ShortestRouteService`, versioned graph caches, historical-memory aggregation, and retained V1 map-matching/event-detection services.

## 19. Database Architecture

Runtime is configured for PostgreSQL with PostGIS. SQLAlchemy supplies ORM access; Alembic contains live-ingestion, live-map index, and Geo V2 network migrations. Current models/tables are:

| Table/model | Purpose |
|---|---|
| `regions` / `Region` | Region/silo identity, pincode, center, segment count |
| `segments` / `Segment` | Shared road-segment identity and physical metadata |
| `geo_segment_metadata` / `GeoSegmentMetadata` | Versioned OSM identity, nodes, highway metadata, PostGIS geometry |
| `geo_segment_transitions` / `GeoSegmentTransition` | Legal directed segment-to-segment transitions |
| `gps_pings` / `GPSPing` | Append-only map-matched or trusted observations |
| `live_ingestion_batches` / `LiveIngestionBatch` | Idempotent receipt, hash, source/run/batch identity, counts and network identity |
| `segment_current_state` / `SegmentCurrentState` | Latest per-segment live projection |
| `segment_historical_memory` / `HistoricalMemory` | Per-segment/hour baseline for retained V1 and fallback use |
| `segment_predictions` / `SegmentPrediction` | Predicted label, probability map, model version, baseline/deviation trace |
| `live_scenarios` / `LiveScenario` | Separate controlled scenario ground truth |
| `events` / `Event` | Retained V1 detected/ground-truth event records |
| `fl_round_records` / `FLRoundRecord` | Retained regional FL contribution history |

Prediction uniqueness is `(source_id, run_id, segment_id, timestamp, model_version)`. Batch uniqueness is `(source_id, run_id, batch_id)`. Geometry uses PostGIS `LINESTRING` SRID 4326 in PostgreSQL and a portable textual representation in tests.

Core-table migration provenance is incomplete in the visible Alembic history; initial tables may depend on the DB initialization/seeding workflow. This is **not verified in current repository** as a complete from-empty migration chain.

## 20. Frontend Architecture

```text
frontend/src/
|-- main.tsx
|-- App.tsx                         React Router and lazy pages
|-- pages/
|   |-- TrafficMap/index.tsx        current operational map/demo/route UI
|   |-- Dashboard/index.tsx
|   |-- Prediction/index.tsx        retained manual 10-feature endpoint UI
|   |-- Federated/index.tsx         static artifact visualization
|   |-- Training/index.tsx          static training artifacts
|   |-- Analysis/index.tsx
|   |-- Results/index.tsx
|   `-- About/index.tsx
|-- components/
|   |-- map/
|   |   |-- AnimatedVehicleLayer.tsx
|   |   |-- MapLegend.tsx
|   |   |-- SegmentPopup.tsx
|   |   |-- segmentGeometry.ts
|   |   |-- segmentStyles.ts
|   |   `-- vehicleAnimation.ts
|   |-- prediction/
|   |-- layout/
|   |-- charts/
|   |-- cards/
|   `-- common/
`-- services/
    |-- api/{client,liveMapApi,demoApi,routeApi,...}.ts
    `-- parsers/csvParser.ts
```

State is primarily local React state plus TanStack Query server state. There is no Redux/Zustand/global domain store. Axios is used for APIs. Leaflet owns map rendering. Controlled demo state, route points, layer flags, selected objects, local timelines, and freshness are held by `TrafficMap`.

## 21. API Inventory

All v1 paths use the `/api/v1` prefix.

| Method | Endpoint | Purpose | Current use |
|---|---|---|---|
| `GET` | `/` | Service identity and docs link | Basic root response |
| `GET` | `/health` | Liveness response | Returns `status: ok`; no DB/model deep check |
| `GET` | `/segments` | List legacy or Geo V2 network segments | Traffic Map static geometry; optional `network_source` |
| `GET` | `/segments/{segment_id}` | Retrieve one legacy segment | Retained detail API |
| `GET` | `/segments/{segment_id}/neighbors` | Retrieve denormalized legacy neighbors | Retained V1 support |
| `POST` | `/ingest/gps` | Map-match one device trajectory and trigger V1 detection | Retained legacy ingestion |
| `POST` | `/ingest/live/batch` | Authenticated idempotent trusted live batch | External live/simulator ingestion |
| `GET` | `/ingest/live/current-state` | Read latest current-state rows | Diagnostics/current state |
| `GET` | `/live-map/snapshot` | Normalized current vehicles, segments, predictions, events | Traffic Map polling |
| `POST` | `/live-scenarios` | Create controlled scenario rows | Scenario API, separate truth |
| `GET` | `/live-scenarios` | List active scenarios | Scenario inspection |
| `POST` | `/demo/geo-v2/runs` | Create route-bound controlled run | Traffic Map demo |
| `GET` | `/demo/geo-v2/runs/{run_id}` | Read demo status | Demo diagnostics |
| `POST` | `/demo/geo-v2/runs/{run_id}/step` | Advance 120 simulated seconds and infer | Traffic Map demo clock |
| `DELETE` | `/demo/geo-v2/runs/{run_id}` | Stop in-process run | Demo reset |
| `POST` | `/prediction/infer/geo-v2` | Single current Geo V2 inference | Current model API |
| `POST` | `/prediction/infer/batch` | Current Geo V2 batch inference, max 500 | Batch model API/demo internals |
| `POST` | `/prediction/infer` | Retained older telemetry inference | Compatibility/V1 path |
| `POST` | `/predict` | Retained manual 10-feature prediction | Frontend Prediction page; not current Geo V2 contract |
| `POST` | `/routes/shortest` | Coordinate-based directed shortest-distance route | Current Traffic Map routing |
| `POST` | `/routes` | Legacy segment-ID event-penalty route | Retained V1 routing, not map default |
| `POST` | `/routes/refresh-graph` | Refresh legacy graph cache | Administrative/development utility, unauthenticated |
| `GET` | `/events` | List retained detected events with best-effort route | Dashboard/events path |
| `GET` | `/federated/status` | In-memory legacy global-model status | Limited observability |
| `GET` | `/metrics` | Segment/event/region dashboard counts | Dashboard |

Only `/ingest/live/batch` has the `X-Live-Ingest-Key` mechanism. CORS currently permits all origins/methods/headers. The application is therefore a local/research implementation, not a hardened public API.

## 22. Testing and Verification

Current read-only collection on 2026-08-25 found:

- **117 backend tests collected** across 24 `test_*.py` modules.
- **46 frontend tests listed** by constrained Vitest discovery.
- `from app.main import app` imported successfully.

The full current suites were not executed during this documentation-only audit. The promoted artifact's stored verification receipt records 100 backend and 26 frontend tests passing at artifact finalization, plus frontend build and runtime artifact load passing. Those are reproducibility receipts for that artifact, not current HEAD's expanded suite counts.

Test coverage includes API health/config, map matching, legacy event detection/routing, adaptive aggregation, historical memory, live ingestion/idempotency, live map, simulation, Geo V2 network, feature contract, model loading, inference, training, robust selection, scripts, repositories, route behavior, and route APIs. Frontend tests cover TrafficMap, vehicle animation, segment styles/geometry, freshness state, API parsing, and prediction result rendering.

Current test fixtures mainly use in-memory SQLite and plain objects. They do not by themselves prove PostgreSQL/PostGIS deployment behavior. A read-only current audit verified the configured PostGIS network contains 2,968 matching metadata rows and 11,259 transitions.

Recommended verification commands are documented under [How to Run](#29-how-to-run). API smoke testing can use FastAPI `/docs`, `/api/v1/health`, a live snapshot after ingestion, and route requests against the selected network.

## 23. Performance and Resource Profile

### 23.1 Measured or Stored Evidence

| Measurement | Verified value | Scope |
|---|---:|---|
| Frozen model single-row CPU inference | Mean `0.4139735 ms` over 1,000 measured calls after 20 warmups | Model store scaling + prediction/probability serialization; excludes HTTP, DB, and browser |
| Approximate model-call throughput | `2415.61 calls/s` | Same local CPU artifact benchmark |
| Selected training run duration | `656.6938375 s` | Stored artifact value; hardware not recorded in that file |
| Generated telemetry geometry validation | 30,000/30,000 valid; maximum distance about `0.000745 m` under 1 m tolerance | Synthetic position-to-LineString alignment, not real GPS accuracy |

### 23.2 Configured or Behavioral, Not Benchmarked

- Live tick interval default: 4 seconds.
- Controlled demo simulation cadence: 120 simulated seconds per backend step.
- Live batch maximum default: 2,000 observations.
- The controlled demo supports 250 or 1,000 vehicles.
- The frontend caps demo marker rendering at 250 while the backend can simulate 1,000.
- Route response includes per-request `computation_time_ms`, but no aggregate route-latency benchmark is stored.
- Graphs are cached by network source/version, but startup/graph-construction timing is **Not verified in current repository**.
- End-to-end ingest-to-map latency is **Not verified in current repository**.
- Database write/read throughput is **Not verified in current repository**.
- Backend/browser memory usage for 250 or 1,000 vehicles is **Not verified in current repository**.

Configured capacity or successful test behavior must not be presented as measured production capacity.

## 24. Current Limitations

- Training telemetry and event schedules are synthetic, although geometry is OSM-grounded.
- Live demonstrations use simulated vehicles, not deployed roadside/mobile telemetry.
- The promoted data is extremely imbalanced; accuracy masks weak minority performance.
- Diversion recall is zero in the stored full-test result; construction recall is low.
- The current model is not approved for unattended safety-critical decisions.
- Current coordinate routing minimizes distance, not predicted traffic, current speed, density, confidence, or live ETA.
- Alternative routing requires explicit predicted-segment exclusions and user action.
- The controlled scenario affects simulation physics and is not independent real-world validation.
- Demo runs are process-local and disappear on backend restart.
- Live updates use polling, not a push channel.
- Demo vehicle rendering is capped at 250 markers.
- The trusted batch API uses one shared API key; most APIs are unauthenticated and CORS is unrestricted.
- The legacy ingestion background task is in-process and non-durable.
- V1 detected events have no complete close-out/expiry lifecycle and can accumulate.
- Current tests are mainly portable/in-memory and do not constitute a full PostGIS deployment test.
- No real roadside deployment, independent traffic authority feed, CCTV analysis, or hardware sensor integration is present.
- No differential privacy, secure aggregation, formal security analysis, or adversarial FL protection is implemented.
- Some retained docs/endpoints/artifacts describe older 10-feature or Gaussian/V1 generations.
- A complete measured startup, route, DB, browser-memory, and end-to-end latency profile is not available.

## 25. What Is Real Versus Demonstration

| Component | Current implementation | Demonstration/simulation | Future |
|---|---|---|---|
| GPS telemetry | Validated ingestion and persistence are real software | Current supplied telemetry is generated/simulated | Independent real mobile/fleet/roadside feeds |
| Road network | Real OSM-derived Beeramguda geometry and PostGIS topology | Vehicle traffic on it is synthetic | Periodic OSM updates and broader production networks |
| ML inference | Real frozen PyTorch artifact, scaling, probabilities, persistence | Trained/evaluated on synthetic scenario traffic | Real incident calibration and external validation |
| Federated training | Real eight-region local optimization and parameter aggregation experiment | Clients are logical/offline research clients | Independently administered secure clients |
| Vehicle movement | Real simulator and map interpolation code | Vehicles are synthetic; browser motion is visual interpolation | Real tracked vehicles |
| Accident scenario | Separate scripted traffic disturbance | Controlled synthetic accident | Verified external incident feed |
| Congestion scenario | Separate scripted traffic disturbance | Controlled synthetic congestion | Measured real congestion episodes |
| Routing | Real directed Dijkstra over persisted OSM topology | Used to define demo corridor | Live cost calibration and alternatives |
| Traffic-aware rerouting | Explicit exclusion reroute only | User can avoid abnormal predicted segments | Automatic prediction/ETA-weighted routing |
| CCTV | Not implemented | None | Optional future multimodal input |
| Roadside sensors | Not deployed | Simulator substitutes observations | Physical roadside/edge deployment |

## 26. Current Versus Historical

| Component | Current | Historical | Evidence |
|---|---|---|---|
| Dataset | `geo_v2_ml_v1_fixed_contract_v2`, 332,416 rows/split, OSM-grounded synthetic telemetry | V1 `fedrouteai_dataset`, about 491K pings on 130 synthetic-grid segments; old paper 30,195 samples | Current manifests/artifact vs `data/raw/`, old IEEE results |
| Model | Geo V2 23->64->32->8 MLP, round 45 | Gaussian local baseline; generic 10-feature MLP; old 27-feature practical candidate | `config.py`, active checkpoint, `model_store.py` |
| Features | Ordered 23-feature `history_spatial_strong` | 10-feature ratios; full 27-feature `history_spatial`; stale 27-feature prose | Active checkpoint and scaler |
| Federation | Eight-region robust offline training, bounded adaptive weights | Flower/Gaussian V1 and older FedAvg/AdaptiveFedAvg 30-round experiments | Active artifact config vs `results/`, `federated_clients/` |
| Network | 2,968 OSM/PostGIS canonical segments, 11,259 transitions | 130-segment synthetic V1 network | Geo V2 metadata/database vs `data/raw/fedrouteai_dataset` |
| Routing | Traffic Map uses directed coordinate shortest-distance route | Legacy segment-ID event-penalty routing retained | `routeApi.ts`, `shortest_route.py`, `routes.py` |
| Map | React/Leaflet Traffic Map with live snapshots and controlled demo | Earlier dashboard/static concepts | `TrafficMap/index.tsx` |
| Research paper | Historical experiment/reference | Reports old 30-round model/dataset metrics | `docs/docs1.01/extracted_reference/` |
| Experiments | Active robust artifact directory is current; alternatives are experimental | Root `results/`, old logs, alternate checkpoints | `GEO_V2_MODEL_PATH` selects one artifact |
| Diagrams | `docs/clg_docs/figures/` canonical current replacements | `docs/docs1.01/extracted_reference/figures/` old reference figures | `FIGURE_INVENTORY.md` |

Old-paper accuracy, macro-F1, feature count, parameter count, communication cost, or model architecture must not be assigned to the current artifact unless the current checkpoint metadata confirms it.

## 27. Important Files

| File / directory | Purpose | Current status |
|---|---|---|
| `backend/app/core/config.py` | Runtime model, baseline, network, DB, FL, route, and live settings | Current configuration truth |
| `backend/app/ml/geo_v2/features.py` | Causal feature variants and leakage guards | Current |
| `backend/app/ml/geo_v2/feature_contract.py` | Runtime raw feature trace and 120-second history contract | Current |
| `backend/app/ml/geo_v2/model.py` | Runtime `GeoV2MLP` | Current |
| `backend/app/ml/geo_v2/model_store.py` | Artifact validation, scaling, loading, inference | Current |
| `backend/app/ml/geo_v2/robust_training.py` | Robust regional training and selection | Current training source |
| `backend/app/ml/artifacts/geo_v2/federated/robust-v2-.../` | Promoted model, metrics, provenance, receipts | Current artifact directory |
| `backend/app/services/geo_v2/runtime_inference.py` | Context trace and batch inference | Current; module docstring incorrectly says 27 features |
| `backend/app/services/geo_v2/prediction_service.py` | Repository-backed inference/persistence | Current |
| `backend/app/services/geo_v2/simulation.py` | Directed geometry-aware synthetic vehicle simulation | Current |
| `backend/app/services/geo_v2/demo_runtime.py` | Route-bound demo lifecycle and label scrubbing | Current |
| `backend/app/services/live_ingestion/service.py` | Trusted batch validation/idempotency/current state | Current |
| `backend/app/services/live_map/service.py` | Snapshot assembly | Current |
| `backend/app/services/routing/shortest_route.py` | Current coordinate distance routing | Current |
| `backend/app/services/road_graph/geo_v2_graph_cache.py` | Versioned directed route graph | Current |
| `backend/app/models/` | SQLAlchemy database contract | Current |
| `backend/app/schemas/` | Separate Pydantic API contract | Current |
| `backend/app/api/v1/router.py` | Endpoint registration | Current |
| `frontend/src/pages/TrafficMap/index.tsx` | Operational map, route, demo UI | Current |
| `frontend/src/services/api/liveMapApi.ts` | Snapshot/network client contracts | Current |
| `frontend/src/services/api/routeApi.ts` | Current shortest-route client | Current |
| `frontend/src/services/api/demoApi.ts` | Controlled-demo client | Current |
| `data/geo_v2/beeramguda_roads.osm.json` | Cached OSM source | Current network source |
| `data/geo_v2/fedrouteai_dataset_geo_v2_ml_v1/` | Preserved source Geo V2 dataset | Current lineage source |
| `data/geo_v2/fedrouteai_dataset_geo_v2_ml_v1_fixed_contract_v2/` | Derived current model dataset | Current, manifest has stale test flag |
| `scripts/geo_v2/` | Import, generation, audit, training, finalization, demo tools | Current tooling |
| `backend/tests/` | Backend verification suite | Current |
| `frontend/src/**/*.test.ts(x)` | Frontend focused tests | Current |
| `run_project.py` | Root local launcher | Current |
| `HOW_TO_RUN_PROJECT.md` | Operational command guide | Current reference |
| `docs/clg_docs/figures/build_figures.py` | Reproducible report figure generator | Current documentation tooling |
| `docs/clg_docs/figures/FIGURE_INVENTORY.md` | Current figure names/evidence | Current |
| `docs/docs1.01/` | Old IEEE and formatting/reference material | Historical/reference |
| `results/` | Earlier FL experiment results | Historical/experimental |

## 28. Research and College Documentation Status

### 28.1 Research Paper

The old IEEE material under `docs/docs1.01/`, `docs/doc1.00/`, and assembled paper directories records an earlier experiment generation. It reports different dataset size, model parameters, federation rounds, and metrics. It also states that data and deployment are simulated. It remains useful for literature framing and historical experiment provenance, not current runtime architecture.

Current source has evolved to Geo V2, causal historical/spatial features, an OSM/PostGIS canonical network, a promoted round-45 23-feature MLP, live snapshots, and directed route-bound demonstration. Old diagrams must not be used as current evidence. The current replacement strategy keeps old reference figures untouched and creates current SVG masters plus PDF/PNG derivatives under `docs/clg_docs/figures/`.

### 28.2 College Documentation

`docs/clg_docs/` is the current college-report production line. It contains the institutional report format, report generator, content/format audits, current technical figure generator, and SVG/PNG/PDF outputs. SVG is the editable master format; PNG is used for DOCX insertion; PDF is the vector/report derivative.

The college report is intended to document the current implementation, but source and artifact metadata remain the final authority. Five UI/demo screenshot positions are intentional placeholders because verified screenshots were unavailable; they must not be replaced with fabricated screenshots.

## 29. How to Run

### 29.1 Prerequisites

- Python 3.12+ is the documented target; the inspected local environment used Python 3.13.2.
- Node.js/npm for the React frontend.
- PostgreSQL with PostGIS.
- A local `backend/.env` based on `.env.example`.
- A non-secret placeholder such as `<LOCAL_LIVE_INGEST_KEY>` in documentation; never commit real secrets.

### 29.2 Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r backend\requirements.txt

Set-Location frontend
npm install
Set-Location ..
```

Configure conceptually:

- PostgreSQL host, port, database, user, and password.
- `LIVE_INGEST_API_KEY=<LOCAL_LIVE_INGEST_KEY>` for external trusted ingestion.
- Optional `VITE_API_BASE_URL=http://localhost:8000` for newer frontend API clients.
- Keep current `GEO_V2_MODEL_PATH`, baseline path, network source, and network version aligned unless deliberately changing artifacts.

### 29.3 Start Application

```powershell
python run_project.py
```

This starts Uvicorn at `127.0.0.1:8000` and Vite at `127.0.0.1:5173`. API docs are at `http://localhost:8000/docs`.

Useful launcher modes:

```powershell
python run_project.py --with-simulator
python run_project.py --simulator-only --simulator-ticks 10
python run_project.py --backend-only
```

For database-backed trusted ingestion, apply migrations and configure the key before using ingestion mode:

```powershell
Set-Location backend
$env:PYTHONPATH = "."
..\.venv\Scripts\python.exe -m alembic upgrade head
Set-Location ..
$env:LIVE_INGEST_API_KEY = "<LOCAL_LIVE_INGEST_KEY>"
python run_project.py --backend-only --with-ingestion --simulator-ticks 10
```

Import the current OSM network when provisioning an empty database:

```powershell
Set-Location backend
$env:PYTHONPATH = "."
..\.venv\Scripts\python.exe ..\scripts\geo_v2\import_network.py
```

### 29.4 Verification

```powershell
Set-Location backend
$env:PYTHONPATH = "."
..\.venv\Scripts\python.exe -m pytest tests -v
..\.venv\Scripts\python.exe -c "from app.main import app"

Set-Location ..\frontend
npm test
npm run lint
npm run build
```

## 30. Common Development Workflows

1. **Start application:** configure PostGIS and run `python run_project.py`.
2. **Inspect map:** open `http://localhost:5173/map`; enable live mode and verify the network/snapshot identity.
3. **Run live telemetry:** use launcher simulator/ingestion modes or `scripts/geo_v2/live_demo.py` with a placeholder local API key.
4. **Inspect predictions:** select a road on the Traffic Map or call `/api/v1/prediction/infer/geo-v2`; verify model version and feature trace.
5. **Calculate route:** select origin/destination on the map; inspect distance, speed-limit duration, segment order, coverage, and warnings.
6. **Run controlled route demonstration:** use a route at least 1.5 km long, select scenario/vehicle count/speed, start, and compare separate telemetry, prediction, and scenario layers.
7. **Run tests:** execute backend pytest, frontend Vitest, import check, lint, and production build.
8. **Rebuild documentation figures:** from repository root run `.\.venv\Scripts\python.exe docs\clg_docs\figures\build_figures.py`; this updates documentation assets only and should be done only when regeneration is intended.

## 31. Current Architecture Diagrams

Each listed figure currently has SVG, PNG, and PDF forms under `docs/clg_docs/figures/{svg,png,pdf}/`, except that the inventory omits master filenames for 6.1-6.3 while matching files are present.

| Figure | Filename stem | Purpose | Source of truth |
|---|---|---|---|
| 4.1 | `fig_4_1_overall_architecture` | Offline/runtime zones and complete system | Current source/config/artifact |
| 4.2 | `fig_4_2_federated_learning` | Eight clients and aggregation | Current training/artifact metadata |
| 4.3 | `fig_4_3_regional_client_server` | Client/server round and raw-data boundary | Current training architecture |
| 4.4 | `fig_4_4_end_to_end_pipeline` | Runtime inference plus separate routing branch | Current services/APIs |
| 4.5 | `fig_4_5_geo_v2_features` | Exact 23-feature contract | Active artifact/scaler/source |
| 4.6 | `fig_4_6_historical_memory` | Causal prehistory and shifted windows | Feature contract/builders |
| 4.7 | `fig_4_7_osm_postgis` | OSM import and canonical network | Network source/repository |
| 4.8 | `fig_4_8_directed_network` | Segment graph and legal transitions | Network/graph code |
| 4.9 | `fig_4_9_backend_architecture` | API/service/repository/model boundaries | Backend source |
| 4.10 | `fig_4_10_frontend_architecture` | React API state and Leaflet layers | Frontend source |
| 4.11 | `fig_4_11_routing` | Directed distance route and prediction inspection | `shortest_route.py`, route API |
| 5.1 | `fig_5_1_live_ingestion` | Append-only ingestion/current projections | Live ingestion source |
| 5.2 | `fig_5_2_frozen_mlp` | Frozen runtime model | Active checkpoint/model code |
| 6.1 | `fig_6_1_model_validation` | Frozen model metrics | Active artifact metrics |
| 6.2 | `fig_6_2_confusion_matrix` | Frozen confusion matrix | Active artifact data |
| 6.3 | `fig_6_3_test_evidence` | Verification evidence | Tests/artifact receipt |
| 7.1 | `fig_7_1_deployment` | Local deployment topology | Runbook/config/source |

The 13 canonical current-architecture replacement figures were verified as non-empty SVG/PDF/PNG assets. PNGs are 2,400 pixels wide and corresponding PDFs are one page. Old figures in `docs/docs1.01/extracted_reference/figures/` are style/composition references only.

## 32. Project Evolution

The repository supports this concise implementation evolution without assigning unverified dates:

```text
V1 synthetic 130-segment network
    -> rule/event-signature detection and Gaussian/early FL concepts
    -> generic 10-feature PyTorch MLP experiments
    -> Geo V2 OSM-grounded dataset and canonical network
    -> causal current + historical + spatial feature variants
    -> full 27-feature practical federated candidate
    -> fixed-contract 23-feature history_spatial_strong robust candidate
    -> round-45 promoted frozen artifact
    -> PostgreSQL/PostGIS network and live ingestion/current projections
    -> React/Leaflet dynamic Traffic Map
    -> directed coordinate shortest-distance routing
    -> deterministic route-bound controlled demonstration
    -> current college-report architecture figures
```

Git history confirms that Geo V2/live-system and directed routing milestones preceded the current college documentation, and current diagram replacements were then regenerated and gathered. The latest inspected commit is documentation-focused rather than a new runtime model release.

## 33. Future Work

### CURRENT

- Frozen 23-feature Geo V2 MLP with eight classes.
- Eight-region offline federated experiment and artifact provenance.
- OSM/PostGIS canonical directed network.
- Validated live ingestion, persistence, prediction snapshots, and map.
- Directed shortest-distance route with post-route prediction inspection.
- Explicit abnormal-segment exclusion reroute.
- Normal/congestion/accident controlled route demonstration.

### PLANNED OR CANDIDATE FUTURE WORK

- Calibrated traffic/prediction-aware route costs and automatic rerouting.
- Live ETA based on measured speed and confidence-aware uncertainty.
- Real mobile/fleet/roadside telemetry and independently verified incidents.
- Larger and more diverse cities, networks, weather, and event datasets.
- Better minority-class sampling/modeling, especially diversion and construction.
- Spatiotemporal/GNN models over the directed network after robust baselines.
- Durable queue/broker for ingestion-triggered asynchronous work.
- Persistent multi-process demo orchestration if needed.
- Stronger API authentication/authorization, restricted CORS, audit logging, and deployment hardening.
- Secure aggregation, differential privacy, and independently operated federation only after concrete threat-model design.
- Optional CCTV/video integration as a future multimodal extension, not a current dependency.
- Full PostGIS integration/performance testing and measured resource profiles.

## 34. Consistency Notes and Unresolved Ambiguities

The following ambiguities were found and must remain visible:

- `runtime_inference.py` says “27-feature” in its module docstring, but the configured artifact, scaler, model store, and current figures agree on 23 features.
- The fixed-contract manifest says the test split was not derived, but a final test CSV and matching receipt exist after one-time finalization.
- Old architecture/README/AI-context files contain Gaussian, 10-feature, 17-test, and 130-segment statements that describe earlier generations.
- The repository retains both current coordinate distance routing and older event-penalty segment routing; only the former is used by Traffic Map.
- The visible Alembic history does not establish a fully verified from-empty migration chain for every foundational table.
- Current collection finds 117 backend and 46 frontend tests; the active artifact receipt records the smaller suites that existed at artifact finalization.
- `final_model.pt`, alternate candidates, calibration datasets, old results, and duplicate paper trees are retained but are not configured as the current runtime artifact.
- Complete current end-to-end performance, memory, and production-load measurements are not verified.

# AI QUICK CONTEXT

**PROJECT:** FedRouteAI, a GPS-derived road-state prediction, dynamic map, directed routing, and controlled-demonstration system.

**CURRENT VERSION:** Geo V2 with causal 120-second feature construction; branch `clg_docs1.05`, inspected HEAD `fa08bae13459a72b02f5862819c95bbaeaa7ac1b` on 2026-08-25.

**MODEL:** Frozen PyTorch MLP `23 -> 64 -> 32 -> 8` with BatchNorm, ReLU, dropout 0.2, LogSoftmax, and 4,072 trainable parameters. Current model version ends in `r45` and is loaded from the configured robust Geo V2 artifact.

**FEATURE CONTRACT:** Exact ordered 23-feature `history_spatial_strong`: six current traffic values, two cyclical hour values, three road metadata values, three normal baselines, three baseline ratios, two prior-window means, two trends, low-speed persistence, and directed-neighbor speed delta. Labels/scenario/event/vehicle identity are forbidden.

**DATASET:** `geo_v2_ml_v1_fixed_contract_v2`, derived from `geo_v2_ml_v1`; OSM-grounded synthetic telemetry, eight regions, 332,416 feature rows per split, severe class imbalance. It is not real GPS incident data.

**NETWORK:** `osm_geo_v2` / `beeramguda-osm-20260506`; 2,968 canonical PostGIS segments, 11,259 directed transitions, 1,301 accepted OSM ways.

**FEDERATED CLIENTS:** Eight logical geographic clients (`REGION_01..REGION_08`), local gradient training, bounded adaptive aggregation, maximum 50 rounds, two local epochs, selected round 45. This is an offline/simulated federation, not a secure deployed multi-organization federation.

**BACKEND:** FastAPI with API -> service -> repository -> model as intended dependency direction; SQLAlchemy/Pydantic are separate. Geo V2 inference, live ingestion, live map, simulation, graph caching, and routing are current major paths.

**FRONTEND:** React 19 + TypeScript + Vite + TanStack Query + Axios + Leaflet. Traffic Map polls snapshots and has separate network, telemetry, prediction, vehicle, event, and route layers.

**DATABASE:** PostgreSQL/PostGIS. Current entities cover regions, segments, Geo V2 metadata/transitions, GPS observations, live batch receipts, current state, predictions, scenarios, events, historical memory, and FL records.

**ROUTING:** Current Traffic Map route is directed Dijkstra with distance cost, coordinate snapping, ordered segment IDs, LineString geometry, and speed-limit duration. Predictions are inspected afterward. Explicit segment exclusions support a user-requested alternative. Do not call the default route traffic-aware.

**LIVE SYSTEM:** Trusted live batch API with one API key, payload-hash idempotency, append-only observations, current-state projection, frozen-model inference, persisted predictions, and snapshot polling.

**DEMONSTRATION:** Deterministic route-bound Geo V2 simulation with 250/1,000 vehicle modes and normal/congestion/accident scenarios. Scenario labels and event IDs are scrubbed before inference. Scenario behavior is not model ground truth.

**CURRENT LIMITATIONS:** Synthetic telemetry, extreme class imbalance, weak diversion/construction recall, no safety-critical approval, distance-only default routing, no real roadside deployment, no secure aggregation/differential privacy, process-local demo registry, polling UI, limited authentication, and incomplete performance/load evidence.

**IMPORTANT CURRENT FILES:** `backend/app/core/config.py`, `backend/app/ml/geo_v2/`, current robust artifact directory, `backend/app/services/geo_v2/`, `backend/app/services/live_ingestion/`, `backend/app/services/live_map/`, `backend/app/services/routing/shortest_route.py`, `frontend/src/pages/TrafficMap/index.tsx`, `data/geo_v2/`, `scripts/geo_v2/`, and `docs/clg_docs/figures/FIGURE_INVENTORY.md`.

**HISTORICAL MATERIAL:** `docs/docs1.01/`, `docs/doc1.00/`, old paper builds/diagrams, root `results/`, old Gaussian/10-feature artifacts, V1 130-segment dataset, parts of `README.md`, `about_project.md`, `CLAUDE.md`, and `docs/architecture.md`.

## RULES FOR FUTURE AI ASSISTANTS

1. Treat current source code as truth.
2. Treat current model artifact metadata as truth.
3. Treat current dataset manifest as truth, while noting the documented stale final-test flag.
4. Do not use old paper architecture as current architecture.
5. Do not claim simulated telemetry is real-world telemetry.
6. Do not claim scenario metadata is model ground truth.
7. Do not claim routing is traffic-aware unless implementation confirms it.
8. Do not invent metrics.
9. Do not modify frozen artifacts without explicit instruction.
10. Preserve reproducibility.

## Inspection Basis

This reference was compiled after inspecting the current Git branch/HEAD/status and representative files across:

- `backend/app/api/`, `core/`, `db/`, `models/`, `schemas/`, `repositories/`, `services/`, and `ml/geo_v2/`;
- the configured promoted model checkpoint and its config, scaler, schema, metrics, provenance, performance, verification, and final-test receipt;
- current Geo V2 source/fixed-contract manifests, feature tables, OSM cache metadata, and spatial validation;
- PostgreSQL/PostGIS network counts and current ORM/network repository behavior;
- `frontend/src/pages/TrafficMap`, map components, API clients, package configuration, and tests;
- `scripts/geo_v2/`, retained V1 scripts, `federated_clients/`, and current run workflows;
- backend/frontend test discovery and backend import behavior;
- current architecture/routing/data documentation, college report maps/audits, and current figure inventory;
- old IEEE/paper/reference trees and retained experiment results for historical classification only.

Major current components identified are the promoted Geo V2 MLP and feature contract, eight-client robust federated training, OSM/PostGIS directed network, trusted live ingestion/current state, persisted runtime inference, React/Leaflet Traffic Map, directed distance routing, and route-bound controlled simulation.

Unresolved ambiguities are recorded in [Consistency Notes and Unresolved Ambiguities](#34-consistency-notes-and-unresolved-ambiguities). No unverified value was promoted as current fact.
