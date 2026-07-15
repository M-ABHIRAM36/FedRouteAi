from app.services.event_detection.signature_extractor import BehavioralSignature
from app.services.event_detection.pattern_matcher import match_event
from app.services.event_detection.event_signatures import EVENT_SIGNATURES


def test_all_event_signatures_are_matchable():
    """Every defined pattern should match itself best when given its own
    exact target ratios — a basic correctness check on the distance metric."""
    for event_type, sig in EVENT_SIGNATURES.items():
        signature = BehavioralSignature(
            segment_id="TEST",
            speed_ratio=sig["speed_mult"],
            density_ratio=sig["density_mult"],
            uturn_ratio=sig["uturn_mult"],
            variance_ratio=sig["speed_variance_mult"],
            sample_size=100,
        )
        result = match_event(signature)
        assert result.event_type == event_type, f"expected {event_type}, got {result.event_type}"
        assert result.confidence > 0.9


def test_normal_signature_is_not_significant():
    signature = BehavioralSignature(
        segment_id="TEST", speed_ratio=1.0, density_ratio=1.0,
        uturn_ratio=1.0, variance_ratio=1.0, sample_size=100,
    )
    result = match_event(signature)
    # a "normal" signature should be far from every event pattern's target
    assert result.confidence < 0.9
