# Data Models

Two parallel representations on purpose — see `docs/architecture.md`
for why. Kept in sync manually today; if they drift enough to hurt,
consider generating one from the other (Pydantic can generate from
SQLAlchemy models via various community tools) — not done by default
here since explicit is easier to reason about at this project's size.

## ORM (`backend/app/models/`) — the database

- **Region** — one federated-learning silo (`region_id`, `pincode`, center coords)
- **Segment** — the fundamental unit; the road between two intersections
- **GPSPing** — one raw (map-matched) GPS observation
- **Event** — a detected OR ground-truth road event
- **HistoricalMemory** — per-segment, per-hour-of-day normal baseline
- **FLRoundRecord** — one region's contribution to one FL aggregation
  round (data quality, loss, sample count, mean feature vector, data
  timestamp) — this is what lets `adaptive_aggregation.py` compute
  historical_similarity and temporal_recency against a region's own
  past rounds instead of treating every round as identical

Exact column lists: read the model files directly, they're short and
the docstring on each explains its role — that's more likely to stay
accurate than a second copy of the schema here.

## Pydantic (`backend/app/schemas/`) — the API contract

- **SegmentOut** — what `/segments` returns (unpacks `neighbor_segments`
  from the DB's `;`-joined string into a real list)
- **GPSPingIn / GPSBatchIn** — what a mobile client POSTs to `/ingest/gps`.
  Deliberately no per-ping `device_id` — a batch IS one device's
  trajectory (`GPSBatchIn.device_id`), so a second identity field per
  ping would only ever redundantly repeat that value or silently
  disagree with it. An earlier version of this schema had one; it was
  removed after it turned out to be both required-but-unused by
  `ingest.py` and actively misleading in tests (see `docs/architecture.md`).
- **EventOut** — THE contract from the project spec:
  `{segment_id, event, confidence, affected_neighbors, recommended_route}`
- **RouteRequest / RouteResponse** — `/routes` input/output
- **ClientRoundSummary / GlobalModelStatus** — FL observability, admin-only

## Synthetic dataset ↔ these models

`scripts/dataset_generator/` produces CSVs with the SAME column names as
the ORM models above (deliberately) — `scripts/seed_db.py` loads them
with a near 1:1 field mapping. If you add a column to a model, add the
matching column to the dataset generator too, or seeding will break —
this was tested end-to-end (130 segments / 8 regions / 3,035 memory
rows / 23 events all load cleanly) but it's a manual sync, not codegen.
