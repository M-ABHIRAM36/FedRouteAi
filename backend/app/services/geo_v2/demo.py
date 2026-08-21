"""Scheduled five-hour demonstration scenario for Geo V2."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta
from enum import Enum

from app.core.constants import EventType
from app.services.geo_v2.simulation import GeoV2Simulation


class DemoPhase(str, Enum):
    NORMAL = "NORMAL"
    CONGESTION = "CONGESTION"
    CONGESTION_ACCIDENT = "CONGESTION+ACCIDENT"
    CONSTRUCTION_CONGESTION = "CONSTRUCTION+CONGESTION"
    RECOVERY = "RECOVERY"
    COMPLETE = "COMPLETE"


@dataclass(frozen=True, slots=True)
class ScheduledDemo:
    simulation: GeoV2Simulation
    segment_id: str

    @classmethod
    def install(cls, simulation: GeoV2Simulation, segment_id: str) -> ScheduledDemo:
        start = simulation.config.start_time
        simulation.schedule_event(
            EventType.CONGESTION,
            segment_id,
            start_time=start + timedelta(hours=1),
            duration_minutes=180,
            severity=0.75,
            event_id="DEMO_CONGESTION",
        )
        simulation.schedule_event(
            EventType.ACCIDENT,
            segment_id,
            start_time=start + timedelta(hours=2),
            duration_minutes=60,
            severity=1.0,
            event_id="DEMO_ACCIDENT",
        )
        simulation.schedule_event(
            EventType.CONSTRUCTION,
            segment_id,
            start_time=start + timedelta(hours=3),
            duration_minutes=60,
            severity=0.8,
            event_id="DEMO_CONSTRUCTION",
        )
        return cls(simulation, segment_id)

    @property
    def phase(self) -> DemoPhase:
        elapsed = self.simulation.state.current_time - self.simulation.config.start_time
        hour = elapsed.total_seconds() / 3600.0
        if hour < 1:
            return DemoPhase.NORMAL
        if hour < 2:
            return DemoPhase.CONGESTION
        if hour < 3:
            return DemoPhase.CONGESTION_ACCIDENT
        if hour < 4:
            return DemoPhase.CONSTRUCTION_CONGESTION
        if hour < 5:
            return DemoPhase.RECOVERY
        return DemoPhase.COMPLETE
