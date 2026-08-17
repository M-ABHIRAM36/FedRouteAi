# Beeramguda Geo V2 OSM Source

`beeramguda_roads.osm.json` is a cached OpenStreetMap Overpass response used
to build the geographically grounded synthetic telemetry network. Runtime and
automated tests do not download OSM data.

- Source: OpenStreetMap contributors, ODbL
- Overpass mirror: `https://overpass.kumi.systems/api/interpreter`
- Query: `[out:json][timeout:300];way[highway](17.505,78.287,17.530,78.312);out body geom;`
- Requested bounding box: south `17.505`, west `78.287`, north `17.530`, east `78.312`
- OSM base timestamp: recorded inside the response

The normalizer filters the response to drivable highway classes and preserves
all source vertices, OSM way/node identifiers, legal one-way direction, and
available road attributes. This is geographically grounded synthetic
telemetry, not real GPS data.
