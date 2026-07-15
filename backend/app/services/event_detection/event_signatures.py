"""
Event Signatures (Event Memory pattern definitions)
------------------------------------------------------
Same table used to generate the synthetic training dataset
(scripts/generate_dataset.py) — reused here unchanged so the live
detector is matching against EXACTLY the patterns the data was labeled
with. If you retrain against real incident data later, recompute these
multipliers from real before/after statistics instead of guessing them.
--------------------
One config table defines every non-normal event type as a set of
multipliers applied to a segment's OWN normal baseline. This is
intentional: it means "add a new event type" = "add one row here",
and it doubles as the literal Event Memory pattern definitions the
main FedRouteAI system is supposed to match live signatures against.

Multiplier semantics (all relative to that segment's normal baseline
at the same hour of day):
  speed_mult            : average speed multiplier during the event
  density_mult          : vehicle-count multiplier ON the affected segment
  uturn_mult            : u-turn-rate multiplier ON the affected segment
  speed_variance_mult   : how much jerkier/less consistent speeds are
  neighbor_density_mult : vehicle-count multiplier on NEIGHBORING segments
                           (models traffic redistribution / rerouting)
  duration_min_range    : (min, max) minutes an instance of this event lasts
"""

EVENT_SIGNATURES = {
    "congestion": dict(
        speed_mult=0.55, density_mult=1.8, uturn_mult=1.3,
        speed_variance_mult=1.2, neighbor_density_mult=1.1,
        duration_min_range=(45, 120),
        description="Organic heavy traffic build-up, no obstruction.",
    ),
    "road_block": dict(
        speed_mult=0.10, density_mult=0.15, uturn_mult=2.5,
        speed_variance_mult=1.5, neighbor_density_mult=1.6,
        duration_min_range=(30, 180),
        description="Full closure — most vehicles avoid/turn back before entering.",
    ),
    "road_damage": dict(
        speed_mult=0.70, density_mult=1.1, uturn_mult=1.2,
        speed_variance_mult=2.2, neighbor_density_mult=1.0,
        duration_min_range=(180, 900),
        description="Pothole/surface damage — erratic braking, persists for hours-to-a-day.",
    ),
    "construction": dict(
        speed_mult=0.60, density_mult=0.9, uturn_mult=1.6,
        speed_variance_mult=1.3, neighbor_density_mult=1.15,
        duration_min_range=(240, 1440),
        description="Lane reduction from ongoing construction work.",
    ),
    "flood": dict(
        speed_mult=0.25, density_mult=0.5, uturn_mult=2.0,
        speed_variance_mult=1.8, neighbor_density_mult=1.4,
        duration_min_range=(60, 300),
        description="Waterlogging — only triggered on flood_prone segments.",
    ),
    "accident": dict(
        speed_mult=0.10, density_mult=0.6, uturn_mult=1.8,
        speed_variance_mult=1.6, neighbor_density_mult=1.3,
        duration_min_range=(15, 45),
        description="Sudden short blockage, sharp onset and recovery.",
    ),
    "diversion": dict(
        speed_mult=1.0, density_mult=0.3, uturn_mult=1.0,
        speed_variance_mult=1.0, neighbor_density_mult=1.7,
        duration_min_range=(60, 240),
        description="Segment itself closed upstream; neighbors absorb its flow.",
    ),
}

EVENT_TYPES = list(EVENT_SIGNATURES.keys())
