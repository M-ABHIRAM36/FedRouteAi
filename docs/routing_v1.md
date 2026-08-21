# Routing V1

Routing V1 adds coordinate-based route planning to the existing Traffic Map.
It is accurately described as OSM/PostGIS directed shortest-path routing with
Geo V2 prediction awareness. It is not traffic-aware or AI-optimized routing.

## Architecture

`POST /api/v1/routes/shortest` follows the existing API to service to
repository layering. The endpoint passes validated coordinates to the routing
service. `GeoV2Repository` loads the persisted network, including its PostGIS
LineString geometry and `GeoSegmentTransition` rows. A process-local cache is
keyed by network source and version, so the graph is not rebuilt per request.

The graph uses road segments as nodes and persisted directed transitions as
edges. Dijkstra minimizes segment distance. Origin and destination coordinates
are projected onto the nearest persisted LineString and rejected when no road
is within the configured snapping radius. Returned geometry concatenates the
actual ordered OSM segment geometry rather than drawing a straight line.

## Prediction Inspection

After the shortest path is calculated, the latest available Geo V2 prediction
for each route segment is loaded for the requested live source and run. Counts
and warnings are informational only. Predictions do not alter edge costs,
exclude roads, or trigger rerouting in V1.

## API Summary

The request supplies origin, destination, active network source/version, and
optional live source/run identity. The response includes snapped points,
ordered segment IDs, GeoJSON LineString geometry, distance, estimated duration
from persisted speed limits, computation time, and prediction counts/warnings.

## Future Extension

The distance cost is intentionally isolated from prediction inspection. A
future version can add explicit congestion or event penalties, road-block
exclusion, alternatives, and dynamic rerouting without changing the persisted
topology or coordinate selection contract.
