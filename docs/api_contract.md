# API Contract (v1)

Base path: `/api/v1`. Full interactive docs at `/docs` once the server
is running (FastAPI auto-generates these from the Pydantic schemas —
treat this file as a map, not the source of truth; `/docs` always wins
if they disagree).

| Method | Path | Purpose | Status |
|---|---|---|---|
| GET | `/health` | Liveness check | ✅ working |
| GET | `/segments` | List segments, optional `?region_id=` filter | ✅ working |
| GET | `/segments/{id}` | One segment | ✅ working |
| GET | `/segments/{id}/neighbors` | Adjacent segments | ✅ working |
| POST | `/ingest/gps` | Batch GPS ping upload | ✅ working — map-matches, persists, and triggers background event detection (see `tests/test_ingest_and_detection.py` for the full loop) |
| GET | `/events` | Currently active detected events | ✅ working — including a computed `recommended_route` per event |
| POST | `/routes` | Compute a route, avoiding active events by default | ✅ working, uses the cached graph (see `graph_cache.py`) |
| POST | `/routes/refresh-graph` | Manually invalidate the cached graph | ✅ working |
| GET | `/federated/status` | Current global model round number | ⚠️ returns real round data but `participating_regions` isn't tracked yet — query `FLRoundRecord` directly for per-region history in the meantime |

## The core output object (`EventOut`)

This is the literal JSON contract from the original project spec:

```json
{
  "event_id": "EVT_0001",
  "segment_id": "HYD_SEG_1023",
  "event": "construction",
  "confidence": 0.94,
  "affected_neighbors": ["HYD_SEG_1022", "HYD_SEG_1024"],
  "recommended_route": ["HYD_SEG_1018", "HYD_SEG_1050", "HYD_SEG_1024"],
  "start_time": "2026-07-06T14:00:00",
  "end_time": "2026-07-06T18:00:00"
}
```

`recommended_route` is now populated for real: `api/v1/endpoints/events.py`
routes between the affected segment's neighbors using the cached graph,
with every currently-active event's segment penalized — the same logic
`/routes` uses directly. It comes back `[]` when there aren't at least
two affected neighbors to route between, or no path exists once events
are penalized (a genuine dead end, not a bug).
