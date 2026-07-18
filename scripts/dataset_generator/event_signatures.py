"""
event_signatures.py  (V2)
--------------------------
One config table defines every non-normal event type as a set of
multipliers applied to a segment's OWN normal baseline. This is
intentional: it means "add a new event type" = "add one row here",
and it doubles as the literal Event Memory pattern definitions the
main FedRouteAI system is supposed to match live signatures against.

V2 additions (these keys are read only by the generator, not by the live system):

  onset_min       : minutes from event start until full severity is reached
  peak_min        : minutes of full-severity effect (not including onset/decay)
  decay_min       : minutes from end of peak until full recovery
  road_type_weights : sampling weights per road_type for selecting the primary
                      segment (fixes generator leakage — events are no longer
                      placed randomly regardless of road type)
  preferred_hours : list of hour buckets this event is most likely to START in
                    (from HOUR_BUCKETS in generate_dataset.py)

Multiplier semantics (all relative to that segment's normal baseline
at the same hour of day — UNCHANGED from V1):
  speed_mult            : average speed multiplier during the event
  density_mult          : vehicle-count multiplier ON the affected segment
  uturn_mult            : u-turn-rate multiplier ON the affected segment
  speed_variance_mult   : how much jerkier/less consistent speeds are
  neighbor_density_mult : vehicle-count multiplier on NEIGHBORING segments
                          (models traffic redistribution / rerouting)
  duration_min_range    : (min, max) minutes an instance of this event lasts
                          (total = onset + peak + decay; peak fills the remainder)
"""

EVENT_SIGNATURES = {
    "congestion": dict(
        # ── Multipliers (unchanged from V1) ──────────────────────────
        speed_mult=0.55, density_mult=1.8, uturn_mult=1.3,
        speed_variance_mult=1.2, neighbor_density_mult=1.1,
        duration_min_range=(45, 120),
        description="Organic heavy traffic build-up, no obstruction.",
        # ── V2 lifecycle ─────────────────────────────────────────────
        onset_min=15,       # traffic builds gradually
        peak_min=None,      # fills the remainder of duration
        decay_min=20,       # clears slowly after peak
        # ── V2 road type affinity ────────────────────────────────────
        road_type_weights={"arterial": 0.50, "collector": 0.35,
                           "residential": 0.10, "highway_link": 0.05},
        # ── V2 preferred start hours ─────────────────────────────────
        preferred_hours=["rush_am", "rush_pm"],   # congestion is a rush-hour phenomenon
    ),

    "road_block": dict(
        speed_mult=0.10, density_mult=0.15, uturn_mult=2.5,
        speed_variance_mult=1.5, neighbor_density_mult=1.6,
        duration_min_range=(30, 180),
        description="Full closure — most vehicles avoid/turn back before entering.",
        onset_min=5,        # road blocks are discovered quickly
        peak_min=None,
        decay_min=10,       # clearance is relatively fast once decided
        road_type_weights={"arterial": 0.50, "collector": 0.30,
                           "residential": 0.15, "highway_link": 0.05},
        preferred_hours=["rush_am", "rush_pm", "daytime"],  # VIP movement, protests
    ),

    "road_damage": dict(
        speed_mult=0.70, density_mult=1.1, uturn_mult=1.2,
        speed_variance_mult=2.2, neighbor_density_mult=1.0,
        duration_min_range=(180, 900),
        description="Pothole/surface damage — erratic braking, persists for hours-to-a-day.",
        onset_min=5,        # damage is pre-existing, discovered immediately
        peak_min=None,
        decay_min=0,        # NO decay: potholes persist until repaired
        road_type_weights={"residential": 0.25, "collector": 0.40,
                           "arterial": 0.25, "highway_link": 0.10},
        preferred_hours=["daytime", "rush_am", "rush_pm", "shoulder"],  # any time
    ),

    "construction": dict(
        speed_mult=0.60, density_mult=0.9, uturn_mult=1.6,
        speed_variance_mult=1.3, neighbor_density_mult=1.15,
        duration_min_range=(240, 1440),
        description="Lane reduction from ongoing construction work.",
        onset_min=30,       # setup takes time
        peak_min=None,
        decay_min=30,       # teardown takes time
        road_type_weights={"collector": 0.40, "arterial": 0.30,
                           "residential": 0.20, "highway_link": 0.10},
        preferred_hours=["daytime", "shoulder"],  # construction rarely at rush hour
    ),

    "flood": dict(
        speed_mult=0.25, density_mult=0.5, uturn_mult=2.0,
        speed_variance_mult=1.8, neighbor_density_mult=1.4,
        duration_min_range=(60, 300),
        description="Waterlogging — only triggered on flood_prone segments.",
        onset_min=20,       # water rises slowly
        peak_min=None,
        decay_min=45,       # drains slowly
        road_type_weights=None,   # None → use flood_prone flag, ignore road type
        preferred_hours=["daytime", "rush_pm", "shoulder"],  # monsoon events any time
    ),

    "accident": dict(
        speed_mult=0.10, density_mult=0.6, uturn_mult=1.8,
        speed_variance_mult=1.6, neighbor_density_mult=1.3,
        duration_min_range=(15, 45),
        description="Sudden short blockage, sharp onset and recovery.",
        onset_min=3,        # sudden — nearly instantaneous
        peak_min=None,
        decay_min=15,       # clears when emergency services arrive
        road_type_weights={"arterial": 0.40, "collector": 0.30,
                           "highway_link": 0.20, "residential": 0.10},
        preferred_hours=["rush_am", "rush_pm", "daytime"],  # peak hours = higher accident rate
    ),

    "diversion": dict(
        speed_mult=1.0, density_mult=0.3, uturn_mult=1.0,
        speed_variance_mult=1.0, neighbor_density_mult=1.7,
        duration_min_range=(60, 240),
        description="Segment itself closed upstream; neighbors absorb its flow.",
        onset_min=10,       # rerouting takes time to communicate to drivers
        peak_min=None,
        decay_min=20,       # gradual as remaining drivers learn alternate route
        road_type_weights={"arterial": 0.60, "collector": 0.30,
                           "residential": 0.05, "highway_link": 0.05},
        preferred_hours=["daytime", "rush_am", "rush_pm"],
    ),
}

EVENT_TYPES = list(EVENT_SIGNATURES.keys())

# Hour bucket definitions (used by generate_dataset.py plan_events_v2)
# Format: (inclusive_start_hour, inclusive_end_hour, sampling_weight)
# weight=0.0 means events NEVER start in this bucket
HOUR_BUCKETS: dict[str, tuple[int, int, float]] = {
    "rush_am":  (8,  10, 4.0),   # 4× more likely than daytime baseline
    "daytime":  (11, 16, 1.5),   # moderate probability
    "rush_pm":  (17, 20, 4.0),   # 4× more likely
    "shoulder": (6,   7, 0.8),   # slightly less likely (less traffic)
    "shoulder2":(21, 22, 0.5),   # late evening, low
    "night":    (23,  5, 0.0),   # FORBIDDEN — no events at near-zero traffic hours
}
