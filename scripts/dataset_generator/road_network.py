"""
road_network.py
----------------
Builds a synthetic-but-geospatially-real road network:
  - Anchored at a real city center (default: Hyderabad, 17.3850N 78.4867E)
  - Node spacing defined in METERS, then converted to lat/lon correctly
  - Irregular (not a perfect grid): jittered node positions, some edges
    dropped, a few long diagonal "arterial" roads added
  - Segments get realistic attributes (lanes, width, max speed, name)
  - Segments are grouped into N regions (KMeans on midpoints) — these
    regions are what the federated-learning "clients" will be built from

NOTE: This is a stand-in for a real OSMnx pull (`ox.graph_from_place(...)`).
This sandbox has no internet access to the OpenStreetMap Overpass API, so
this generates a structurally realistic network instead. Swapping in a
real city graph later just means replacing `build_road_network()`'s output
with segments read from OSMnx — every downstream function only needs the
same segments.csv schema.
"""

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from geo_utils import offset_latlon, haversine_m

ROAD_TYPES = [
    # (type_name, weight, lanes_range, width_m_range, max_speed_kmph)
    ("residential",   0.45, (1, 2), (5, 7),  30),
    ("collector",     0.30, (2, 3), (7, 10), 45),
    ("arterial",      0.20, (3, 4), (10, 14), 60),
    ("highway_link",  0.05, (4, 6), (14, 20), 80),
]

STREET_SUFFIXES = ["Road", "Street", "Marg", "Cross Road", "Main Road", "Lane"]
STREET_STEMS = [
    "Banjara", "Jubilee", "Kondapur", "Gachibowli", "Madhapur", "Ameerpet",
    "Kukatpally", "Begumpet", "Somajiguda", "Punjagutta", "Miyapur",
    "Tarnaka", "Uppal", "LB Nagar", "Dilsukhnagar", "Secunderabad",
    "Himayath", "Manikonda", "Nallagandla", "Attapur",
]


def _pick_road_type(rng: np.random.Generator):
    names = [r[0] for r in ROAD_TYPES]
    weights = [r[1] for r in ROAD_TYPES]
    idx = rng.choice(len(names), p=weights)
    return ROAD_TYPES[idx]


def build_road_network(
    center_lat: float = 17.3850,
    center_lon: float = 78.4867,
    grid_n: int = 9,             # grid_n x grid_n intersections
    spacing_m: float = 220.0,    # avg block size in meters
    jitter_m: float = 35.0,      # how "non-grid" the layout looks
    drop_edge_frac: float = 0.12,
    n_arterials: int = 4,
    n_regions: int = 8,
    seed: int = 42,
):
    rng = np.random.default_rng(seed)

    # ---- 1. Place intersections (nodes) on a jittered grid, in METERS
    #         first, then convert to lat/lon with the correct per-axis
    #         formula (this is where lat/lon asymmetry matters). ----
    nodes = {}
    node_id = 0
    grid_index_to_id = {}
    for i in range(grid_n):
        for j in range(grid_n):
            dx = (i - grid_n / 2) * spacing_m + rng.normal(0, jitter_m)
            dy = (j - grid_n / 2) * spacing_m + rng.normal(0, jitter_m)
            lat, lon = offset_latlon(center_lat, center_lon, dx_east_m=dx, dy_north_m=dy)
            nodes[node_id] = (lat, lon)
            grid_index_to_id[(i, j)] = node_id
            node_id += 1

    # ---- 2. Base grid edges (horizontal + vertical neighbors), then
    #         randomly drop some to look less like a perfect grid. ----
    edges = []
    for i in range(grid_n):
        for j in range(grid_n):
            a = grid_index_to_id[(i, j)]
            if i + 1 < grid_n:
                b = grid_index_to_id[(i + 1, j)]
                edges.append((a, b))
            if j + 1 < grid_n:
                b = grid_index_to_id[(i, j + 1)]
                edges.append((a, b))

    keep_mask = rng.random(len(edges)) > drop_edge_frac
    edges = [e for e, keep in zip(edges, keep_mask) if keep]

    # ---- 3. A few long diagonal "arterial" roads across the city ----
    for _ in range(n_arterials):
        a = rng.integers(0, node_id)
        b = rng.integers(0, node_id)
        if a != b:
            edges.append((a, b))

    # ---- 4. Build the segments table with realistic attributes ----
    rows = []
    seg_counter = 1
    region_prefix = "HYD"
    for (a, b) in edges:
        lat1, lon1 = nodes[a]
        lat2, lon2 = nodes[b]
        length_m = haversine_m(lat1, lon1, lat2, lon2)
        if length_m < 15:      # skip degenerate near-zero-length edges
            continue
        road_type, _, lanes_range, width_range, max_speed = _pick_road_type(rng)
        lanes = int(rng.integers(lanes_range[0], lanes_range[1] + 1))
        width = round(float(rng.uniform(*width_range)), 1)
        name = f"{rng.choice(STREET_STEMS)} {rng.choice(STREET_SUFFIXES)}"
        segment_id = f"{region_prefix}_SEG_{seg_counter:04d}"
        seg_counter += 1

        rows.append(dict(
            segment_id=segment_id,
            road_name=name,
            road_type=road_type,
            node_start=a,
            node_end=b,
            start_lat=lat1, start_lon=lon1,
            end_lat=lat2, end_lon=lon2,
            segment_length_m=round(length_m, 1),
            number_of_lanes=lanes,
            road_width_m=width,
            max_speed_kmph=max_speed,
            road_direction=str(rng.choice(["bidirectional", "one_way"], p=[0.8, 0.2])),
            flood_prone=bool(rng.random() < 0.12),   # tags a subset of segments as
                                                       # low-lying, used later so flood
                                                       # events land somewhere plausible
        ))

    segments = pd.DataFrame(rows)

    # ---- 5. Neighbor list: any segment sharing a node with another ----
    node_to_segs = {}
    for _, r in segments.iterrows():
        node_to_segs.setdefault(r.node_start, []).append(r.segment_id)
        node_to_segs.setdefault(r.node_end, []).append(r.segment_id)

    def neighbors_of(row):
        neigh = set(node_to_segs.get(row.node_start, [])) | set(node_to_segs.get(row.node_end, []))
        neigh.discard(row.segment_id)
        return ";".join(sorted(neigh))

    segments["neighbor_segments"] = segments.apply(neighbors_of, axis=1)

    # ---- 6. Partition into N regions via KMeans on segment midpoints ----
    mid_lat = (segments.start_lat + segments.end_lat) / 2
    mid_lon = (segments.start_lon + segments.end_lon) / 2
    coords = np.column_stack([mid_lat.values, mid_lon.values])
    km = KMeans(n_clusters=n_regions, random_state=seed, n_init=10).fit(coords)
    segments["region_id"] = [f"REGION_{c+1:02d}" for c in km.labels_]

    # pincode-like label per region, purely cosmetic/realistic
    pincode_base = 500001
    region_to_pincode = {
        r: pincode_base + i * 7 for i, r in enumerate(sorted(segments.region_id.unique()))
    }
    segments["pincode"] = segments["region_id"].map(region_to_pincode)

    regions = (
        segments.groupby("region_id")
        .agg(
            segment_count=("segment_id", "count"),
            center_lat=("start_lat", "mean"),
            center_lon=("start_lon", "mean"),
            pincode=("pincode", "first"),
        )
        .reset_index()
    )

    return segments, regions


if __name__ == "__main__":
    segments, regions = build_road_network()
    print(segments.shape, "segments")
    print(regions)
    print(segments.head(3).T)
