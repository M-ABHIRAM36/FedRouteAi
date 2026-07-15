# Event Signatures — the Event Memory reference patterns

Defined once in `backend/app/services/event_detection/event_signatures.py`
and reused unchanged by both the synthetic dataset generator and the
live pattern matcher, so training data and detection logic can never
drift apart silently.

| event_type | speed | density | u-turns | variance | neighbor spillover | typical duration |
|---|---|---|---|---|---|---|
| congestion | ×0.55 | ×1.8 | ×1.3 | ×1.2 | ×1.1 | 45–120 min |
| road_block | ×0.10 | ×0.15 | ×2.5 | ×1.5 | ×1.6 | 30–180 min |
| road_damage | ×0.70 | ×1.1 | ×1.2 | ×2.2 | ×1.0 | 3–15 hr |
| construction | ×0.60 | ×0.9 | ×1.6 | ×1.3 | ×1.15 | 4–24 hr |
| flood | ×0.25 | ×0.5 | ×2.0 | ×1.8 | ×1.4 | 1–5 hr |
| accident | ×0.10 | ×0.6 | ×1.8 | ×1.6 | ×1.3 | 15–45 min |
| diversion | ×1.0 | ×0.3 | ×1.0 | ×1.0 | ×1.7 | 1–4 hr |

All multipliers are relative to that segment's OWN historical baseline
at the same hour of day — never a fleet-wide or city-wide average.

`pattern_matcher.py::match_event()` computes a weighted distance between
a live `BehavioralSignature` and each row above, picks the closest, and
converts distance to a 0–1 confidence. `tests/test_event_detection.py`
verifies every pattern matches itself with >0.9 confidence, so this
table and the matcher can't silently drift out of sync.

**When you get real incident data**: recompute these multipliers from
actual before/after speed and volume deltas instead of keeping the
synthetic-simulation values — the structure (which features matter per
event type) will very likely still be right, but the exact numbers
should come from reality once you have it.
