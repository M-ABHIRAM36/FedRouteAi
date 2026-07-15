"""
generate_dataset.py
--------------------
Orchestrates the full FedRouteAI synthetic dataset build:

  1. Build the road network + regions           (road_network.py)
  2. Simulate 48h of NORMAL traffic on every segment, day + night
  3. Inject 2-4 labeled EVENTS per region, drawn from EVENT_SIGNATURES,
     overwriting the normal pings on the affected segment(s) for the
     event window, and applying a lighter "spillover" effect on
     neighboring segments (traffic redistribution)
  4. Aggregate NORMAL-only pings into per-segment-per-hour historical
     memory (this is what a local/global model actually trains on)
  5. Write:
       global/        -> everything combined (one centralized view)
       federated/*/    -> the SAME data, split per region (8 silos)
       road_network/   -> segments.csv, regions.csv
       event_log.csv   -> ground-truth label table
"""

import os
import shutil
from datetime import datetime, timedelta

import numpy as np
import pandas as pd

from road_network import build_road_network
from traffic_sim import simulate_segment_hour
from event_signatures import EVENT_SIGNATURES, EVENT_TYPES

SEED = 42
SIM_START = datetime(2026, 7, 6, 0, 0, 0)   # a Monday
SIM_HOURS = 48                               # 2 full days: Mon 00:00 -> Wed 00:00
OUT_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data", "raw", "fedrouteai_dataset")
EVENTS_PER_REGION = (2, 4)                   # inclusive random range


def plan_events(segments: pd.DataFrame, regions: pd.DataFrame, rng: np.random.Generator):
    """Pick which segments get which event, when, how severe, for how long.
    Returns a list of event dicts and a lookup of (segment_id, hour_idx) -> event info
    for both primary segments and their spillover neighbors."""
    events = []
    seg_by_region = {r: g for r, g in segments.groupby("region_id")}

    event_id = 1
    for region_id, group in seg_by_region.items():
        n_events = int(rng.integers(EVENTS_PER_REGION[0], EVENTS_PER_REGION[1] + 1))
        flood_capable = group[group.flood_prone]
        for _ in range(n_events):
            event_type = str(rng.choice(EVENT_TYPES))
            if event_type == "flood":
                if len(flood_capable) == 0:
                    event_type = str(rng.choice([e for e in EVENT_TYPES if e != "flood"]))
                    pool = group
                else:
                    pool = flood_capable
            else:
                pool = group

            primary = pool.sample(1, random_state=int(rng.integers(0, 1_000_000))).iloc[0]
            sig = EVENT_SIGNATURES[event_type]
            duration_min = int(rng.integers(*sig["duration_min_range"]))
            duration_hr = max(1, round(duration_min / 60))
            start_hour_idx = int(rng.integers(0, max(SIM_HOURS - duration_hr, 1)))
            severity = float(rng.uniform(0.65, 1.0))

            neighbor_ids = [s for s in primary.neighbor_segments.split(";") if s]

            events.append(dict(
                event_id=f"EVT_{event_id:04d}",
                event_type=event_type,
                region_id=region_id,
                primary_segment_id=primary.segment_id,
                start_time=SIM_START + timedelta(hours=start_hour_idx),
                end_time=SIM_START + timedelta(hours=start_hour_idx + duration_hr),
                duration_hours=duration_hr,
                severity=round(severity, 2),
                affected_neighbors=";".join(neighbor_ids),
                start_hour_idx=start_hour_idx,
                hour_span=list(range(start_hour_idx, start_hour_idx + duration_hr)),
            ))
            event_id += 1

    return events


def build_hour_lookup(events):
    """(segment_id, hour_idx) -> event dict, for O(1) lookups while simulating.
    Two lookups: primary (full effect) and neighbor (spillover effect)."""
    primary_lookup = {}
    neighbor_lookup = {}
    for ev in events:
        for h in ev["hour_span"]:
            primary_lookup[(ev["primary_segment_id"], h)] = ev
            for n in ev["affected_neighbors"].split(";"):
                if n:
                    neighbor_lookup.setdefault((n, h), ev)  # first event wins if overlap
    return primary_lookup, neighbor_lookup


def simulate_all(segments: pd.DataFrame, events, rng: np.random.Generator):
    primary_lookup, neighbor_lookup = build_hour_lookup(events)
    all_rows = []

    for _, seg in segments.iterrows():
        for h in range(SIM_HOURS):
            hour_start = SIM_START + timedelta(hours=h)
            ev = primary_lookup.get((seg.segment_id, h))
            neigh_ev = neighbor_lookup.get((seg.segment_id, h))

            if ev is not None:
                event_arg = dict(type=ev["event_type"], severity=ev["severity"],
                                  signature=EVENT_SIGNATURES[ev["event_type"]])
                rows = simulate_segment_hour(seg, hour_start, rng, event=event_arg)
                for row in rows:
                    row["label"] = ev["event_type"]
                    row["event_id"] = ev["event_id"]
            elif neigh_ev is not None:
                sig = EVENT_SIGNATURES[neigh_ev["event_type"]]
                # spillover: apply neighbor_density_mult only, speed largely unaffected
                boosted_seg = seg.copy()
                rows = simulate_segment_hour(seg, hour_start, rng, event=None)
                extra_n = int(len(rows) and max(0, round(len(rows) * (sig["neighbor_density_mult"] - 1))))
                if extra_n > 0:
                    extra_rows = simulate_segment_hour(seg, hour_start, rng, event=None)[:extra_n]
                    rows += extra_rows
                for row in rows:
                    row["label"] = f'{neigh_ev["event_type"]}_neighbor_effect'
                    row["event_id"] = neigh_ev["event_id"]
            else:
                rows = simulate_segment_hour(seg, hour_start, rng, event=None)
                for row in rows:
                    row["event_id"] = ""

            all_rows.extend(rows)

    return pd.DataFrame(all_rows)


def build_historical_memory(pings: pd.DataFrame) -> pd.DataFrame:
    """Per-segment, per-hour-of-day baseline, computed ONLY from label=='normal' rows."""
    normal = pings[pings.label == "normal"].copy()
    normal["hour_of_day"] = pd.to_datetime(normal.timestamp).dt.hour
    grouped = (
        normal.groupby(["segment_id", "hour_of_day"])
        .agg(
            avg_speed_kmph=("speed_kmph", "mean"),
            std_speed_kmph=("speed_kmph", "std"),
            avg_vehicle_count=("vehicle_id", "nunique"),
            uturn_rate=("is_uturn_flag", "mean"),
            sample_size=("speed_kmph", "count"),
        )
        .reset_index()
    )
    grouped["avg_speed_kmph"] = grouped["avg_speed_kmph"].round(1)
    grouped["std_speed_kmph"] = grouped["std_speed_kmph"].fillna(0).round(2)
    grouped["uturn_rate"] = grouped["uturn_rate"].round(3)
    return grouped


def main():
    rng = np.random.default_rng(SEED)

    if os.path.exists(OUT_DIR):
        shutil.rmtree(OUT_DIR)
    os.makedirs(OUT_DIR)

    print("1/6  Building road network...")
    segments, regions = build_road_network(seed=SEED)
    print(f"     {len(segments)} segments across {len(regions)} regions")

    print("2/6  Planning events...")
    events = plan_events(segments, regions, rng)
    print(f"     {len(events)} labeled events planned "
          f"({', '.join(sorted(set(e['event_type'] for e in events)))})")

    print("3/6  Simulating 48h of GPS pings (normal + injected events)...")
    pings = simulate_all(segments, events, rng)
    print(f"     {len(pings):,} GPS ping rows generated")

    print("4/6  Building historical road memory (from normal pings only)...")
    memory = build_historical_memory(pings)
    print(f"     {len(memory):,} segment-hour memory rows")

    event_log = pd.DataFrame(events).drop(columns=["hour_span"])

    print("5/6  Writing road_network/ and global/ ...")
    os.makedirs(f"{OUT_DIR}/road_network", exist_ok=True)
    segments.drop(columns=["node_start", "node_end"]).to_csv(
        f"{OUT_DIR}/road_network/segments.csv", index=False)
    regions.to_csv(f"{OUT_DIR}/road_network/regions.csv", index=False)

    os.makedirs(f"{OUT_DIR}/global", exist_ok=True)
    pings.to_csv(f"{OUT_DIR}/global/gps_pings_all.csv", index=False)
    # (filter gps_pings_all.csv by the `label` column for normal-only / events-only —
    #  kept as one file instead of three redundant copies to keep the download small)
    memory.to_csv(f"{OUT_DIR}/global/segment_historical_memory.csv", index=False)
    event_log.to_csv(f"{OUT_DIR}/global/event_log.csv", index=False)

    print("6/6  Writing federated/<region>/ splits ...")
    os.makedirs(f"{OUT_DIR}/federated", exist_ok=True)
    for region_id, seg_group in segments.groupby("region_id"):
        region_dir = f"{OUT_DIR}/federated/{region_id}"
        os.makedirs(region_dir, exist_ok=True)
        seg_ids = set(seg_group.segment_id)

        region_pings = pings[pings.segment_id.isin(seg_ids)]
        region_memory = memory[memory.segment_id.isin(seg_ids)]
        region_events = event_log[event_log.region_id == region_id]

        seg_group.drop(columns=["node_start", "node_end"]).to_csv(
            f"{region_dir}/segments.csv", index=False)
        region_pings.to_csv(f"{region_dir}/gps_pings.csv", index=False)
        region_memory.to_csv(f"{region_dir}/segment_historical_memory.csv", index=False)
        region_events.to_csv(f"{region_dir}/event_log.csv", index=False)

    print("\nDone.")
    print(f"Label distribution:\n{pings.label.value_counts()}")
    return segments, regions, pings, memory, event_log


if __name__ == "__main__":
    main()
