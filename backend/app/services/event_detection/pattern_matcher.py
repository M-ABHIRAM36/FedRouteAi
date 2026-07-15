"""
Event Memory Matching
------------------------
Compares a live BehavioralSignature against every known EVENT_SIGNATURES
pattern and returns the best match + confidence, instead of directly
classifying every anomaly from scratch. This is a straightforward
distance metric for Phase 1 (see project scope — pattern-memory
matching, not an end-to-end learned classifier) — swap in something
learned once you have enough labeled real events to train on.

Each feature gets its own NOISE TOLERANCE rather than being compared on
raw ratio units directly. This matters a lot in practice: on a small
live window (a handful of vehicles), u-turn RATE is a rate of a rare
binary event and swings wildly (one extra U-turn among 5 vehicles can
look like a 5x baseline rate), while speed ratio is a mean of a
continuous variable and stays comparatively stable even on small
samples. Without per-feature tolerances, a single noisy feature
dominates the distance and the matcher either always says "no match"
or has to be so loose it stops discriminating between patterns at all.
"""
import math
from dataclasses import dataclass

from app.services.event_detection.event_signatures import EVENT_SIGNATURES
from app.services.event_detection.signature_extractor import BehavioralSignature
from app.core.config import settings

# how many "ratio units" of slack each feature gets before it starts
# meaningfully hurting the match — larger = noisier/less trusted signal
FEATURE_TOLERANCE = dict(speed_ratio=0.15, density_ratio=0.6, uturn_ratio=1.5, variance_ratio=0.5)
FEATURE_WEIGHT = dict(speed_ratio=1.2, density_ratio=1.0, uturn_ratio=0.8, variance_ratio=0.6)


@dataclass
class MatchedEvent:
    event_type: str
    confidence: float
    is_significant: bool  # False if confidence < settings.EVENT_CONFIDENCE_THRESHOLD


def _normalized_distance(sig: BehavioralSignature, pattern: dict) -> float:
    pairs = (
        ("speed_ratio", sig.speed_ratio, pattern["speed_mult"]),
        ("density_ratio", sig.density_ratio, pattern["density_mult"]),
        ("uturn_ratio", sig.uturn_ratio, pattern["uturn_mult"]),
        ("variance_ratio", sig.variance_ratio, pattern["speed_variance_mult"]),
    )
    total_weighted_sq = 0.0
    total_weight = 0.0
    for name, actual, target in pairs:
        normalized = (actual - target) / FEATURE_TOLERANCE[name]
        w = FEATURE_WEIGHT[name]
        total_weighted_sq += w * normalized ** 2
        total_weight += w
    return math.sqrt(total_weighted_sq / total_weight)  # "typical" tolerance-units of deviation


def match_event(sig: BehavioralSignature) -> MatchedEvent:
    best_type, best_dist = None, float("inf")
    for event_type, pattern in EVENT_SIGNATURES.items():
        d = _normalized_distance(sig, pattern)
        if d < best_dist:
            best_dist, best_type = d, event_type

    # Gaussian-shaped falloff in normalized-distance space: a perfect
    # match (0 tolerance-units off) -> confidence 1.0; one tolerance-unit
    # off on average -> ~0.6; two units off -> ~0.14. This replaces a
    # flat linear denominator specifically because linear scoring was
    # either too strict (killed real detections on realistically-noisy
    # small samples) or too loose (stopped discriminating between
    # patterns) — there was no single denominator that did both.
    confidence = math.exp(-0.5 * best_dist ** 2)

    return MatchedEvent(
        event_type=best_type,
        confidence=round(confidence, 3),
        is_significant=confidence >= settings.EVENT_CONFIDENCE_THRESHOLD,
    )
