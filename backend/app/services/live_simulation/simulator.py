"""Persistent, deterministic traffic simulation for the V1 road network.

The simulator is deliberately database-free. Callers provide the existing
Segment ORM objects, rows loaded from segments.csv, or equivalent plain
objects. Generated observations use the existing synthetic GPSPing schema and
can later be grouped by vehicle_id into GPSBatchIn requests.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Mapping, Sequence

import numpy as np

from app.core.config import settings
from app.core.constants import EventType, VehicleType
from app.services.event_detection.event_signatures import EVENT_SIGNATURES
from app.utils.geo_utils import bearing_deg, haversine_m


_BASE_VEHICLES_PER_HOUR = {
    "residential": 6.0,
    "collector": 14.0,
    "arterial": 24.0,
    "highway_link": 34.0,
}
_VEHICLE_TYPES = [member.value for member in VehicleType]
_VEHICLE_WEIGHTS = np.array([0.50, 0.28, 0.17, 0.05])
_VEHICLE_SPEED_ADJUST = {"car": 1.00, "bike": 1.12, "auto": 0.88, "bus": 0.78}
_MIN_SPEED_KMPH = 4.0


@dataclass(frozen=True)
class SimulationConfig:
    """Runtime controls; defaults come from the central application settings."""

    pings_per_tick: int = settings.LIVE_PINGS_PER_TICK
    tick_interval_seconds: float = settings.LIVE_TICK_INTERVAL_SECONDS
    simulation_speed: float = settings.LIVE_SIMULATION_SPEED
    random_seed: int = settings.LIVE_RANDOM_SEED
    start_time: datetime = datetime(2026, 7, 7, 8, 0, 0)
    weather: str = "clear"

    def __post_init__(self) -> None:
        if self.pings_per_tick <= 0:
            raise ValueError("pings_per_tick must be positive")
        if self.tick_interval_seconds <= 0:
            raise ValueError("tick_interval_seconds must be positive")
        if self.simulation_speed <= 0:
            raise ValueError("simulation_speed must be positive")
        if self.weather not in {"clear", "rain", "heavy_rain"}:
            raise ValueError("weather must be clear, rain, or heavy_rain")

    @property
    def simulated_tick_seconds(self) -> float:
        return self.tick_interval_seconds * self.simulation_speed


@dataclass(frozen=True)
class RoadSegment:
    segment_id: str
    region_id: str
    road_type: str
    start_lat: float
    start_lon: float
    end_lat: float
    end_lon: float
    segment_length_m: float
    max_speed_kmph: float
    road_direction: str
    flood_prone: bool
    neighbor_ids: tuple[str, ...]


@dataclass
class VehicleState:
    vehicle_id: str
    vehicle_type: str
    segment_id: str
    position: float
    direction: int
    speed_kmph: float
    is_uturn_flag: bool = False


@dataclass
class SimulationEvent:
    event_id: str
    event_type: str
    segment_id: str
    region_id: str
    start_time: datetime
    end_time: datetime
    severity: float = 1.0

    def is_active(self, at: datetime) -> bool:
        return self.start_time <= at < self.end_time


@dataclass
class RoadSegmentState:
    segment_id: str
    region_id: str
    vehicle_count: int = 0
    density: float = 0.0
    average_speed_kmph: float = 0.0
    traffic_state: str = EventType.NORMAL.value
    available: bool = True
    event_id: str = ""


@dataclass
class SimulationState:
    current_time: datetime
    vehicles: dict[str, VehicleState] = field(default_factory=dict)
    active_events: dict[str, SimulationEvent] = field(default_factory=dict)
    road_segment_states: dict[str, RoadSegmentState] = field(default_factory=dict)
    running: bool = False
    tick_number: int = 0


def _field(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _normal_profile(hour: int, day_of_week: int, weather: str) -> tuple[float, float, float]:
    """The same time/day/weather profile used by V1 traffic_sim.py."""
    if 8 <= hour <= 10 or 17 <= hour <= 20:
        speed_mult, density_mult, uturn_rate = 0.62, 1.7, 0.035
    elif hour >= 23 or hour <= 4:
        speed_mult, density_mult, uturn_rate = 1.08, 0.18, 0.010
    elif 5 <= hour <= 7 or 21 <= hour <= 22:
        speed_mult, density_mult, uturn_rate = 0.90, 0.55, 0.018
    else:
        speed_mult, density_mult, uturn_rate = 0.80, 1.0, 0.022

    density_mult *= {0: 1.00, 1: 1.05, 2: 1.00, 3: 1.05, 4: 1.10, 5: 0.75, 6: 0.55}[day_of_week]
    speed_mult *= {"clear": 1.0, "rain": 0.92, "heavy_rain": 0.80}[weather]
    density_mult *= {"clear": 1.0, "rain": 1.10, "heavy_rain": 1.20}[weather]
    return speed_mult, density_mult, uturn_rate


class LiveTrafficSimulation:
    """Continuously evolves vehicles and traffic state over valid segments."""

    def __init__(self, segments: Sequence[Any], config: SimulationConfig | None = None):
        self.config = config or SimulationConfig()
        self._rng = np.random.default_rng(self.config.random_seed)
        self._segments = self._normalize_segments(segments)
        if not self._segments:
            raise ValueError("at least one road segment is required")
        self._validate_network()
        self.state = SimulationState(current_time=self.config.start_time)
        self._event_counter = 0

    @property
    def segments(self) -> Mapping[str, RoadSegment]:
        return self._segments

    def start(self) -> None:
        """Initialize persistent vehicles. Calling start twice is harmless."""
        if self.state.running:
            return
        if not self.state.vehicles:
            self._initialize_vehicles()
        self.state.running = True
        self._refresh_segment_states()

    def stop(self) -> None:
        self.state.running = False

    def tick(self) -> list[dict[str, Any]]:
        """Advance the clock and world once, then return one observation per vehicle."""
        if not self.state.running:
            raise RuntimeError("simulation must be started before ticking")
        self.state.current_time += timedelta(seconds=self.config.simulated_tick_seconds)
        self.state.tick_number += 1
        self._expire_events()
        self._move_vehicles()
        self._refresh_segment_states()
        return self.generate_batch()

    def generate_batch(self) -> list[dict[str, Any]]:
        """Snapshot the current world using the existing GPSPing synthetic schema."""
        if not self.state.running:
            raise RuntimeError("simulation must be started before generating a batch")
        rows = []
        for vehicle in self.state.vehicles.values():
            segment = self._segments[vehicle.segment_id]
            lat, lon = self._position_on_segment(segment, vehicle.position)
            event = self._event_for_segment(segment.segment_id)
            rows.append({
                "segment_id": segment.segment_id,
                "region_id": segment.region_id,
                "vehicle_id": vehicle.vehicle_id,
                "vehicle_type": vehicle.vehicle_type,
                "lat": round(lat, 7),
                "lon": round(lon, 7),
                "speed_kmph": round(vehicle.speed_kmph, 1),
                "heading_deg": round(self._heading(segment, vehicle.direction), 1),
                "timestamp": self.state.current_time,
                "is_uturn_flag": vehicle.is_uturn_flag,
                "label": event.event_type if event else EventType.NORMAL.value,
                "event_id": event.event_id if event else "",
            })
            vehicle.is_uturn_flag = False
        return rows

    def add_event(
        self,
        event_type: str,
        segment_id: str,
        *,
        duration_minutes: int | None = None,
        severity: float = 1.0,
        event_id: str | None = None,
    ) -> SimulationEvent:
        """Inject an existing V1 event type into the live world."""
        if event_type not in EVENT_SIGNATURES:
            raise ValueError(f"unknown V1 event type: {event_type}")
        if segment_id not in self._segments:
            raise ValueError(f"unknown segment_id: {segment_id}")
        if not 0.0 < severity <= 1.0:
            raise ValueError("severity must be in (0, 1]")
        if event_type == EventType.FLOOD.value and not self._segments[segment_id].flood_prone:
            raise ValueError("flood events require a flood-prone segment")

        signature = EVENT_SIGNATURES[event_type]
        if duration_minutes is None:
            low, high = signature["duration_min_range"]
            duration_minutes = int(self._rng.integers(low, high + 1))
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")

        self._event_counter += 1
        event = SimulationEvent(
            event_id=event_id or f"LIVE_EVT_{self._event_counter:04d}",
            event_type=event_type,
            segment_id=segment_id,
            region_id=self._segments[segment_id].region_id,
            start_time=self.state.current_time,
            end_time=self.state.current_time + timedelta(minutes=duration_minutes),
            severity=severity,
        )
        self.state.active_events[event.event_id] = event
        self._refresh_segment_states()
        return event

    def remove_event(self, event_id: str) -> None:
        self.state.active_events.pop(event_id, None)
        self._refresh_segment_states()

    def summary(self) -> dict[str, Any]:
        batch = self.generate_batch()
        region_distribution = Counter(row["region_id"] for row in batch)
        event_distribution = Counter(row["label"] for row in batch if row["label"] != EventType.NORMAL.value)
        occupied = [state for state in self.state.road_segment_states.values() if state.vehicle_count]
        return {
            "timestamp": self.state.current_time,
            "pings_generated": len(batch),
            "unique_vehicles": len({row["vehicle_id"] for row in batch}),
            "active_road_segments": len(occupied),
            "active_events": len(self.state.active_events),
            "region_distribution": dict(sorted(region_distribution.items())),
            "event_distribution": dict(sorted(event_distribution.items())),
            "average_speed_kmph": round(float(np.mean([row["speed_kmph"] for row in batch])), 2),
            "average_density": round(float(np.mean([state.density for state in occupied])), 2) if occupied else 0.0,
        }

    def _normalize_segments(self, rows: Sequence[Any]) -> dict[str, RoadSegment]:
        result = {}
        for row in rows:
            segment_id = str(_field(row, "segment_id"))
            neighbors = _field(row, "neighbor_segments", "") or ""
            neighbor_ids = tuple(part for part in str(neighbors).split(";") if part)
            result[segment_id] = RoadSegment(
                segment_id=segment_id,
                region_id=str(_field(row, "region_id")),
                road_type=str(_field(row, "road_type")),
                start_lat=float(_field(row, "start_lat")),
                start_lon=float(_field(row, "start_lon")),
                end_lat=float(_field(row, "end_lat")),
                end_lon=float(_field(row, "end_lon")),
                segment_length_m=float(_field(row, "segment_length_m")),
                max_speed_kmph=float(_field(row, "max_speed_kmph")),
                road_direction=str(_field(row, "road_direction", "bidirectional")),
                flood_prone=bool(_field(row, "flood_prone", False)),
                neighbor_ids=neighbor_ids,
            )
        return result

    def _validate_network(self) -> None:
        for segment in self._segments.values():
            if not segment.segment_id or not segment.region_id:
                raise ValueError("every segment requires segment_id and region_id")
            if segment.segment_length_m <= 0 or segment.max_speed_kmph <= 0:
                raise ValueError(f"invalid dimensions for segment {segment.segment_id}")
            unknown = set(segment.neighbor_ids) - self._segments.keys()
            if unknown:
                raise ValueError(f"segment {segment.segment_id} has unknown neighbors: {sorted(unknown)}")

    def _initialize_vehicles(self) -> None:
        segments = list(self._segments.values())
        _, density_mult, _ = _normal_profile(
            self.state.current_time.hour,
            self.state.current_time.weekday(),
            self.config.weather,
        )
        weights = np.array([
            _BASE_VEHICLES_PER_HOUR.get(segment.road_type, 10.0) * density_mult
            for segment in segments
        ])
        weights /= weights.sum()

        chosen = self._rng.choice(len(segments), size=self.config.pings_per_tick, p=weights)
        for index, segment_index in enumerate(chosen, start=1):
            segment = segments[int(segment_index)]
            vehicle_type = str(self._rng.choice(_VEHICLE_TYPES, p=_VEHICLE_WEIGHTS))
            direction = 1 if segment.road_direction == "one_way" or self._rng.random() < 0.5 else -1
            self.state.vehicles[f"LIVE_V_{index:05d}"] = VehicleState(
                vehicle_id=f"LIVE_V_{index:05d}",
                vehicle_type=vehicle_type,
                segment_id=segment.segment_id,
                position=float(self._rng.random()),
                direction=direction,
                speed_kmph=self._target_speed(segment, vehicle_type),
            )

    def _move_vehicles(self) -> None:
        for vehicle in self.state.vehicles.values():
            segment = self._segments[vehicle.segment_id]
            target_speed = self._target_speed(segment, vehicle.vehicle_type)
            # Inertia keeps consecutive observations causal instead of independently sampled.
            previous_weight = 0.20 if self._event_for_segment(segment.segment_id) else 0.65
            vehicle.speed_kmph = previous_weight * vehicle.speed_kmph + (1.0 - previous_weight) * target_speed
            distance_m = vehicle.speed_kmph * 1000.0 / 3600.0 * self.config.simulated_tick_seconds
            vehicle.position += vehicle.direction * distance_m / segment.segment_length_m
            while vehicle.position > 1.0 or vehicle.position < 0.0:
                overflow_m = (vehicle.position - 1.0) * segment.segment_length_m if vehicle.position > 1.0 else -vehicle.position * segment.segment_length_m
                exit_at_end = vehicle.position > 1.0
                self._transition_vehicle(vehicle, segment, exit_at_end, overflow_m)
                segment = self._segments[vehicle.segment_id]

    def _transition_vehicle(self, vehicle: VehicleState, old: RoadSegment, exit_at_end: bool, overflow_m: float) -> None:
        available = [
            self._segments[segment_id]
            for segment_id in old.neighbor_ids
            if self.state.road_segment_states.get(segment_id, RoadSegmentState("", "")).available
        ]
        if not available:
            vehicle.direction *= -1
            vehicle.position = 1.0 if exit_at_end else 0.0
            vehicle.is_uturn_flag = True
            return

        endpoint = (old.end_lat, old.end_lon) if exit_at_end else (old.start_lat, old.start_lon)
        distances = []
        for candidate in available:
            start_distance = haversine_m(*endpoint, candidate.start_lat, candidate.start_lon)
            end_distance = haversine_m(*endpoint, candidate.end_lat, candidate.end_lon)
            distances.append((candidate, start_distance, end_distance))
        minimum = min(min(start, end) for _, start, end in distances)
        connected = [item for item in distances if min(item[1], item[2]) <= minimum + 1.0]
        connected = [
            item for item in connected
            if item[0].road_direction != "one_way" or item[1] <= item[2]
        ]
        if not connected:
            vehicle.direction *= -1
            vehicle.position = 1.0 if exit_at_end else 0.0
            vehicle.is_uturn_flag = True
            return
        candidate, start_distance, end_distance = connected[int(self._rng.integers(0, len(connected)))]
        direction = 1 if start_distance <= end_distance else -1
        vehicle.segment_id = candidate.segment_id
        vehicle.direction = direction
        fraction = min(overflow_m / candidate.segment_length_m, 1.0)
        vehicle.position = fraction if direction == 1 else 1.0 - fraction

    def _target_speed(self, segment: RoadSegment, vehicle_type: str) -> float:
        speed_mult, _, _ = _normal_profile(
            self.state.current_time.hour,
            self.state.current_time.weekday(),
            self.config.weather,
        )
        event = self._event_for_segment(segment.segment_id)
        variance_mult = 1.0
        if event:
            signature = EVENT_SIGNATURES[event.event_type]
            speed_mult *= 1.0 + event.severity * (signature["speed_mult"] - 1.0)
            variance_mult = 1.0 + event.severity * (signature["speed_variance_mult"] - 1.0)
        noise = float(self._rng.normal(1.0, 0.10 * variance_mult))
        speed = segment.max_speed_kmph * speed_mult * _VEHICLE_SPEED_ADJUST[vehicle_type] * noise
        return float(np.clip(speed, _MIN_SPEED_KMPH, segment.max_speed_kmph * 1.15))

    def _refresh_segment_states(self) -> None:
        counts = Counter(vehicle.segment_id for vehicle in self.state.vehicles.values())
        speeds: dict[str, list[float]] = {segment_id: [] for segment_id in self._segments}
        for vehicle in self.state.vehicles.values():
            speeds[vehicle.segment_id].append(vehicle.speed_kmph)

        states = {}
        for segment in self._segments.values():
            event = self._event_for_segment(segment.segment_id)
            count = counts[segment.segment_id]
            density = float(count)
            traffic_state = EventType.NORMAL.value
            available = True
            event_id = ""
            if event:
                signature = EVENT_SIGNATURES[event.event_type]
                density *= 1.0 + event.severity * (signature["density_mult"] - 1.0)
                traffic_state = event.event_type
                event_id = event.event_id
                available = event.event_type != EventType.ROAD_BLOCK.value
            else:
                neighbor_events = [self._event_for_segment(neighbor_id) for neighbor_id in segment.neighbor_ids]
                neighbor_events = [item for item in neighbor_events if item]
                if neighbor_events:
                    density *= max(EVENT_SIGNATURES[item.event_type]["neighbor_density_mult"] for item in neighbor_events)
            states[segment.segment_id] = RoadSegmentState(
                segment_id=segment.segment_id,
                region_id=segment.region_id,
                vehicle_count=count,
                density=round(density, 2),
                average_speed_kmph=round(float(np.mean(speeds[segment.segment_id])), 2) if count else 0.0,
                traffic_state=traffic_state,
                available=available,
                event_id=event_id,
            )
        self.state.road_segment_states = states

    def _event_for_segment(self, segment_id: str) -> SimulationEvent | None:
        active = [
            event for event in self.state.active_events.values()
            if event.segment_id == segment_id and event.is_active(self.state.current_time)
        ]
        return max(active, key=lambda item: item.severity, default=None)

    def _expire_events(self) -> None:
        self.state.active_events = {
            event_id: event for event_id, event in self.state.active_events.items()
            if event.is_active(self.state.current_time)
        }

    @staticmethod
    def _position_on_segment(segment: RoadSegment, position: float) -> tuple[float, float]:
        position = min(max(position, 0.0), 1.0)
        return (
            segment.start_lat + (segment.end_lat - segment.start_lat) * position,
            segment.start_lon + (segment.end_lon - segment.start_lon) * position,
        )

    @staticmethod
    def _heading(segment: RoadSegment, direction: int) -> float:
        if direction == 1:
            return bearing_deg(segment.start_lat, segment.start_lon, segment.end_lat, segment.end_lon)
        return bearing_deg(segment.end_lat, segment.end_lon, segment.start_lat, segment.start_lon)
