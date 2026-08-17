"""Deterministic, database-free traffic simulation on ``CanonicalNetwork``."""

from __future__ import annotations

import math
import random
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from statistics import fmean, pvariance
from typing import Mapping

from app.core.constants import EventType, RoadType, VehicleType
from app.services.event_detection.event_signatures import EVENT_SIGNATURES
from app.services.geo_v2.geometry import interpolate_polyline
from app.services.geo_v2.network import CanonicalNetwork, CanonicalSegment
from app.utils.geo_utils import haversine_m


class TimeProfile(str, Enum):
    NIGHT = "NIGHT"
    EARLY_MORNING = "EARLY_MORNING"
    MORNING_PEAK = "MORNING_PEAK"
    MIDDAY = "MIDDAY"
    EVENING_PEAK = "EVENING_PEAK"
    NIGHT_RECOVERY = "NIGHT_RECOVERY"


_TIME_PROFILE_BY_HOUR = (
    (0, 5, TimeProfile.NIGHT, 1.05, 0.25),
    (5, 7, TimeProfile.EARLY_MORNING, 0.92, 0.55),
    (7, 11, TimeProfile.MORNING_PEAK, 0.58, 1.55),
    (11, 17, TimeProfile.MIDDAY, 0.80, 1.00),
    (17, 21, TimeProfile.EVENING_PEAK, 0.55, 1.65),
    (21, 24, TimeProfile.NIGHT_RECOVERY, 0.88, 0.65),
)
_ROAD_CAPACITY_VPH = {
    RoadType.RESIDENTIAL: 700.0,
    RoadType.COLLECTOR: 1_000.0,
    RoadType.ARTERIAL: 1_400.0,
    RoadType.HIGHWAY_LINK: 1_600.0,
}
_ROAD_DEMAND_WEIGHT = {
    RoadType.RESIDENTIAL: 0.7,
    RoadType.COLLECTOR: 1.1,
    RoadType.ARTERIAL: 1.7,
    RoadType.HIGHWAY_LINK: 1.9,
}
_VEHICLE_SPEED = {
    VehicleType.CAR: 1.0,
    VehicleType.BIKE: 1.08,
    VehicleType.AUTO: 0.88,
    VehicleType.BUS: 0.78,
}
_VEHICLE_TYPES = tuple(VehicleType)
_EVENT_TYPES = frozenset(EventType) - {EventType.NORMAL}
_BLOCKING_TYPES = frozenset({EventType.ROAD_BLOCK})


def time_profile(at: datetime) -> TimeProfile:
    return next(profile for start, end, profile, _, _ in _TIME_PROFILE_BY_HOUR if start <= at.hour < end)


def _profile_factors(at: datetime) -> tuple[float, float]:
    return next((speed, demand) for start, end, _, speed, demand in _TIME_PROFILE_BY_HOUR if start <= at.hour < end)


@dataclass(frozen=True, slots=True)
class SimulationConfig:
    vehicle_count: int = 1_000
    tick_seconds: float = 5.0
    simulation_speed: float = 1.0
    random_seed: int = 42
    start_time: datetime = datetime(2026, 7, 7, 6, 0, 0)

    def __post_init__(self) -> None:
        if self.vehicle_count <= 0:
            raise ValueError("vehicle_count must be positive")
        if self.tick_seconds <= 0 or self.simulation_speed <= 0:
            raise ValueError("tick_seconds and simulation_speed must be positive")

    @property
    def simulated_tick_seconds(self) -> float:
        return self.tick_seconds * self.simulation_speed


@dataclass(slots=True)
class VehicleState:
    vehicle_id: str
    vehicle_type: VehicleType
    segment_id: str
    direction: int
    distance_m: float
    speed_kmph: float
    destination_segment_id: str
    preferred_road_type: RoadType
    recent_segment_ids: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class ScenarioEvent:
    event_id: str
    event_type: EventType
    segment_id: str
    severity: float
    start_time: datetime
    end_time: datetime

    def is_active(self, at: datetime) -> bool:
        return self.start_time <= at < self.end_time


@dataclass(frozen=True, slots=True)
class SegmentFlowState:
    segment_id: str
    profile: TimeProfile
    vehicle_count: int
    density_vehicles_per_km_lane: float
    average_speed_kmph: float
    speed_variance: float
    flow_rate_vph: float
    occupancy: float
    capacity_vehicles: float
    capacity_vph: float
    travel_time_seconds: float
    active_event_types: tuple[EventType, ...]
    upstream_pressure: float
    downstream_pressure: float
    available_for_entry: bool


@dataclass(frozen=True, slots=True)
class TransitionRecord:
    vehicle_id: str
    from_segment_id: str
    to_segment_id: str
    via_node_id: int


@dataclass(slots=True)
class SimulationState:
    current_time: datetime
    tick_number: int = 0
    running: bool = False
    vehicles: dict[str, VehicleState] = field(default_factory=dict)
    active_events: dict[str, ScenarioEvent] = field(default_factory=dict)
    flow_states: dict[str, SegmentFlowState] = field(default_factory=dict)
    last_transitions: list[TransitionRecord] = field(default_factory=list)


class GeoV2Simulation:
    """Moves persistent vehicles over legal directed transitions without routing."""

    def __init__(
        self,
        network: CanonicalNetwork,
        config: SimulationConfig | None = None,
        *,
        segment_context: Mapping[str, Mapping[str, object]] | None = None,
    ) -> None:
        if not network.segments:
            raise ValueError("network requires at least one segment")
        self.network = network
        self.config = config or SimulationConfig()
        self._rng = random.Random(self.config.random_seed)
        self._segments = {segment.segment_id: segment for segment in network.segments}
        self._segment_order = tuple(sorted(self._segments))
        self._context = {key: dict(value) for key, value in (segment_context or {}).items()}
        unknown_context = self._context.keys() - self._segments.keys()
        if unknown_context:
            raise ValueError(f"unknown segment context: {sorted(unknown_context)}")
        self._transitions = {(item.from_segment_id, item.to_segment_id, item.via_node_id) for item in network.transitions}
        self._outgoing: dict[tuple[str, int], list[tuple[str, int, int]]] = defaultdict(list)
        self._upstream: dict[str, set[str]] = defaultdict(set)
        self._downstream: dict[str, set[str]] = defaultdict(set)
        self._index_transitions()
        self._destination_preferences = self._build_destination_preferences()
        self._events: dict[str, ScenarioEvent] = {}
        self._active_events_by_segment: dict[str, tuple[ScenarioEvent, ...]] = {}
        self._propagation_by_segment: dict[str, tuple[float, float]] = {}
        self._event_counter = 0
        self.state = SimulationState(current_time=self.config.start_time)

    @property
    def events(self) -> Mapping[str, ScenarioEvent]:
        return self._events

    def start(self) -> None:
        if not self.state.vehicles:
            self._initialize_vehicles()
        self.state.running = True
        self._refresh_active_events()
        self._refresh_flow_states(Counter())

    def stop(self) -> None:
        self.state.running = False

    def schedule_event(
        self,
        event_type: EventType | str,
        segment_id: str,
        *,
        start_time: datetime | None = None,
        duration_minutes: float | None = None,
        severity: float = 1.0,
        event_id: str | None = None,
    ) -> ScenarioEvent:
        kind = EventType(event_type)
        if kind not in _EVENT_TYPES:
            raise ValueError("normal is a baseline state, not a scenario event")
        if segment_id not in self._segments:
            raise ValueError(f"unknown segment_id: {segment_id}")
        if not 0.0 < severity <= 1.0:
            raise ValueError("severity must be in (0, 1]")
        if kind is EventType.FLOOD and not bool(self._context.get(segment_id, {}).get("flood_prone", False)):
            raise ValueError("flood events require flood_prone in provided segment context")
        if duration_minutes is None:
            low, high = EVENT_SIGNATURES[kind.value]["duration_min_range"]
            duration_minutes = float(self._rng.randint(low, high))
        if duration_minutes <= 0:
            raise ValueError("duration_minutes must be positive")
        self._event_counter += 1
        starts = start_time or self.state.current_time
        event = ScenarioEvent(
            event_id=event_id or f"G2E{self._event_counter:06d}",
            event_type=kind,
            segment_id=segment_id,
            severity=severity,
            start_time=starts,
            end_time=starts + timedelta(minutes=duration_minutes),
        )
        if len(event.event_id) > 20:
            raise ValueError("event_id must fit the ingestion schema (20 characters)")
        if event.event_id in self._events:
            raise ValueError(f"duplicate event_id: {event.event_id}")
        self._events[event.event_id] = event
        self._refresh_active_events()
        if self.state.vehicles:
            self._refresh_flow_states(Counter())
        return event

    def cancel_event(self, event_id: str) -> None:
        self._events.pop(event_id, None)
        self._refresh_active_events()
        if self.state.vehicles:
            self._refresh_flow_states(Counter())

    def tick(self) -> list[dict[str, object]]:
        if not self.state.running:
            raise RuntimeError("simulation must be started before ticking")
        self.state.current_time += timedelta(seconds=self.config.simulated_tick_seconds)
        self.state.tick_number += 1
        self._refresh_active_events()
        crossings: Counter[str] = Counter()
        self.state.last_transitions = []
        for vehicle in self.state.vehicles.values():
            self._move_vehicle(vehicle, crossings)
        self._refresh_flow_states(crossings)
        return self.observations()

    def observations(self) -> list[dict[str, object]]:
        """Return only fields accepted by ``LiveGPSObservationIn``."""
        rows: list[dict[str, object]] = []
        for vehicle in self.state.vehicles.values():
            segment = self._segments[vehicle.segment_id]
            position = interpolate_polyline(
                segment.geometry,
                vehicle.distance_m,
                reverse=vehicle.direction < 0,
            )
            events = self._events_on(segment.segment_id)
            label_event = max(events, key=lambda event: (event.severity, event.event_id), default=None)
            rows.append({
                "observation_id": f"G2-{self.state.tick_number:06d}-{vehicle.vehicle_id}",
                "segment_id": segment.segment_id,
                "region_id": segment.region_id,
                "vehicle_id": vehicle.vehicle_id,
                "vehicle_type": vehicle.vehicle_type.value,
                "lat": round(position.coordinate[1], 8),
                "lon": round(position.coordinate[0], 8),
                "speed_kmph": round(vehicle.speed_kmph, 3),
                "heading_deg": round(position.heading_deg, 3),
                "timestamp": self.state.current_time,
                "is_uturn_flag": False,
                "label": label_event.event_type.value if label_event else EventType.NORMAL.value,
                "event_id": label_event.event_id if label_event else "",
            })
        return rows

    def _index_transitions(self) -> None:
        for source_id, target_id, node_id in self._transitions:
            source = self._segments[source_id]
            target = self._segments[target_id]
            source_direction = 1 if source.end_node_id == node_id else -1
            if source_direction < 0 and source.one_way:
                continue
            target_direction = 1 if target.start_node_id == node_id else -1
            if target_direction < 0 and target.one_way:
                continue
            self._outgoing[(source_id, source_direction)].append((target_id, target_direction, node_id))
            self._upstream[target_id].add(source_id)
            self._downstream[source_id].add(target_id)
        for options in self._outgoing.values():
            options.sort()

    def _initialize_vehicles(self) -> None:
        _, demand = _profile_factors(self.state.current_time)
        weights = [
            _ROAD_DEMAND_WEIGHT[self._segments[segment_id].road_type] * demand
            for segment_id in self._segment_order
        ]
        for index in range(1, self.config.vehicle_count + 1):
            segment_id = self._rng.choices(self._segment_order, weights=weights, k=1)[0]
            segment = self._segments[segment_id]
            direction = 1 if segment.one_way or self._rng.random() < 0.5 else -1
            vehicle_type = self._rng.choices(_VEHICLE_TYPES, weights=(50, 28, 17, 5), k=1)[0]
            destination = self._rng.choice(self._segment_order)
            speed = self._base_target_speed(segment, vehicle_type)
            self.state.vehicles[f"GEO2_V_{index:04d}"] = VehicleState(
                vehicle_id=f"GEO2_V_{index:04d}",
                vehicle_type=vehicle_type,
                segment_id=segment_id,
                direction=direction,
                distance_m=self._rng.random() * segment.length_m,
                speed_kmph=speed,
                destination_segment_id=destination,
                preferred_road_type=self._segments[destination].road_type,
            )

    def _build_destination_preferences(self) -> dict[tuple[str, int, str], float]:
        diagonal_m = max(
            haversine_m(
                self.network.bbox[1],
                self.network.bbox[0],
                self.network.bbox[3],
                self.network.bbox[2],
            ),
            1.0,
        )
        destination_points = {
            segment_id: segment.geometry[len(segment.geometry) // 2]
            for segment_id, segment in self._segments.items()
        }
        preferences = {}
        for target_id, target in self._segments.items():
            for direction in (-1, 1):
                exit_point = target.geometry[-1] if direction > 0 else target.geometry[0]
                for destination_id, destination_point in destination_points.items():
                    distance = haversine_m(
                        exit_point[1],
                        exit_point[0],
                        destination_point[1],
                        destination_point[0],
                    )
                    preferences[(target_id, direction, destination_id)] = min(
                        max(2.0 - distance / diagonal_m, 0.25),
                        2.0,
                    )
        return preferences

    def _move_vehicle(self, vehicle: VehicleState, crossings: Counter[str]) -> None:
        segment = self._segments[vehicle.segment_id]
        target = self._target_speed(segment, vehicle)
        vehicle.speed_kmph = 0.45 * vehicle.speed_kmph + 0.55 * target
        remaining = vehicle.speed_kmph / 3.6 * self.config.simulated_tick_seconds
        transition_limit = 32
        while remaining > 0 and transition_limit > 0:
            available_on_segment = segment.length_m - vehicle.distance_m
            if remaining <= available_on_segment:
                vehicle.distance_m += remaining
                return
            remaining -= available_on_segment
            choice = self._choose_transition(vehicle)
            if choice is None:
                if not segment.one_way:
                    vehicle.direction *= -1
                    vehicle.distance_m = 0.0
                    transition_limit -= 1
                    continue
                vehicle.distance_m = segment.length_m
                vehicle.speed_kmph = 0.0
                return
            target_id, target_direction, via_node_id = choice
            old_id = vehicle.segment_id
            vehicle.recent_segment_ids = (vehicle.recent_segment_ids + [old_id])[-4:]
            vehicle.segment_id = target_id
            vehicle.direction = target_direction
            vehicle.distance_m = 0.0
            segment = self._segments[target_id]
            crossings[target_id] += 1
            self.state.last_transitions.append(
                TransitionRecord(vehicle.vehicle_id, old_id, target_id, via_node_id)
            )
            if target_id == vehicle.destination_segment_id:
                vehicle.destination_segment_id = self._rng.choice(self._segment_order)
                vehicle.preferred_road_type = self._segments[vehicle.destination_segment_id].road_type
            transition_limit -= 1
        if transition_limit == 0:
            vehicle.speed_kmph = 0.0

    def _choose_transition(self, vehicle: VehicleState) -> tuple[str, int, int] | None:
        options = [
            option for option in self._outgoing.get((vehicle.segment_id, vehicle.direction), ())
            if not self._is_blocked(option[0])
        ]
        if not options:
            return None
        weights = []
        for target_id, direction, _ in options:
            target = self._segments[target_id]
            destination_preference = self._destination_preferences[
                (target_id, direction, vehicle.destination_segment_id)
            ]
            road_preference = 1.35 if target.road_type is vehicle.preferred_road_type else 1.0
            revisit_penalty = 0.15 if target_id in vehicle.recent_segment_ids else 1.0
            diversion_penalty = 0.08 if any(
                event.event_type is EventType.DIVERSION for event in self._events_on(target_id)
            ) else 1.0
            weights.append(destination_preference * road_preference * revisit_penalty * diversion_penalty)
        return self._rng.choices(options, weights=weights, k=1)[0]

    def _base_target_speed(self, segment: CanonicalSegment, vehicle_type: VehicleType) -> float:
        speed_factor, _ = _profile_factors(self.state.current_time)
        return segment.max_speed_kmph * speed_factor * _VEHICLE_SPEED[vehicle_type]

    def _target_speed(self, segment: CanonicalSegment, vehicle: VehicleState) -> float:
        speed = self._base_target_speed(segment, vehicle.vehicle_type)
        variance_factor = 1.0
        for event in self._events_on(segment.segment_id):
            signature = EVENT_SIGNATURES[event.event_type.value]
            speed *= 1.0 + event.severity * (signature["speed_mult"] - 1.0)
            variance_factor *= 1.0 + event.severity * (signature["speed_variance_mult"] - 1.0)
        upstream, downstream = self._propagation_pressure(segment.segment_id)
        speed *= max(0.35, 1.0 - 0.12 * upstream - 0.07 * downstream)
        noise_sigma = 0.045 * variance_factor
        speed *= max(0.25, self._rng.gauss(1.0, noise_sigma))
        return min(max(speed, 0.0), segment.max_speed_kmph * 1.12)

    def _refresh_active_events(self) -> None:
        self.state.active_events = {
            event_id: event for event_id, event in self._events.items()
            if event.is_active(self.state.current_time)
        }
        grouped: dict[str, list[ScenarioEvent]] = defaultdict(list)
        for event in self.state.active_events.values():
            grouped[event.segment_id].append(event)
        self._active_events_by_segment = {
            segment_id: tuple(sorted(events, key=lambda event: (event.event_type.value, event.event_id)))
            for segment_id, events in grouped.items()
        }
        pressure: dict[str, list[float]] = defaultdict(lambda: [0.0, 0.0])
        for event in self.state.active_events.values():
            signature = EVENT_SIGNATURES[event.event_type.value]
            redistribution = max(signature["neighbor_density_mult"] - 1.0, 0.0) * event.severity
            upstream_factor = 1.25 if event.event_type in _BLOCKING_TYPES else 0.75
            downstream_factor = 1.35 if event.event_type is EventType.DIVERSION else 1.0
            for segment_id in self._upstream[event.segment_id]:
                pressure[segment_id][0] += redistribution * upstream_factor
            for segment_id in self._downstream[event.segment_id]:
                pressure[segment_id][1] += redistribution * downstream_factor
        self._propagation_by_segment = {
            segment_id: (values[0], values[1]) for segment_id, values in pressure.items()
        }

    def _events_on(self, segment_id: str) -> tuple[ScenarioEvent, ...]:
        return self._active_events_by_segment.get(segment_id, ())

    def _is_blocked(self, segment_id: str) -> bool:
        return any(event.event_type in _BLOCKING_TYPES for event in self._events_on(segment_id))

    def _propagation_pressure(self, segment_id: str) -> tuple[float, float]:
        return self._propagation_by_segment.get(segment_id, (0.0, 0.0))

    def _refresh_flow_states(self, crossings: Counter[str]) -> None:
        vehicles_by_segment: dict[str, list[VehicleState]] = defaultdict(list)
        for vehicle in self.state.vehicles.values():
            vehicles_by_segment[vehicle.segment_id].append(vehicle)
        profile = time_profile(self.state.current_time)
        interval_hours = self.config.simulated_tick_seconds / 3600.0
        states = {}
        for segment_id in self._segment_order:
            segment = self._segments[segment_id]
            vehicles = vehicles_by_segment[segment_id]
            speeds = [vehicle.speed_kmph for vehicle in vehicles]
            count = len(vehicles)
            length_km = segment.length_m / 1000.0
            capacity_vehicles = max(segment.length_m * segment.lanes / 7.5, 1.0)
            capacity_vph = _ROAD_CAPACITY_VPH[segment.road_type] * segment.lanes
            density_factor = 1.0
            capacity_factor = 1.0
            events = self._events_on(segment_id)
            for event in events:
                signature = EVENT_SIGNATURES[event.event_type.value]
                density_factor *= 1.0 + event.severity * (signature["density_mult"] - 1.0)
                if event.event_type is EventType.CONSTRUCTION:
                    capacity_factor *= 1.0 - 0.55 * event.severity
                elif event.event_type in {EventType.ACCIDENT, EventType.FLOOD}:
                    capacity_factor *= 1.0 - 0.75 * event.severity
                elif event.event_type is EventType.ROAD_BLOCK:
                    capacity_factor = 0.0
            capacity_vehicles *= capacity_factor
            capacity_vph *= capacity_factor
            average_speed = fmean(speeds) if speeds else 0.0
            upstream, downstream = self._propagation_pressure(segment_id)
            density = count / max(length_km * segment.lanes, 0.001)
            density *= density_factor * (1.0 + upstream + downstream)
            states[segment_id] = SegmentFlowState(
                segment_id=segment_id,
                profile=profile,
                vehicle_count=count,
                density_vehicles_per_km_lane=density,
                average_speed_kmph=average_speed,
                speed_variance=pvariance(speeds) if len(speeds) > 1 else 0.0,
                flow_rate_vph=crossings[segment_id] / interval_hours if interval_hours else 0.0,
                occupancy=min(count / capacity_vehicles, 1.0) if capacity_vehicles else float(count > 0),
                capacity_vehicles=capacity_vehicles,
                capacity_vph=capacity_vph,
                travel_time_seconds=(segment.length_m / (average_speed / 3.6)) if average_speed > 0 else math.inf,
                active_event_types=tuple(event.event_type for event in events),
                upstream_pressure=upstream,
                downstream_pressure=downstream,
                available_for_entry=not self._is_blocked(segment_id),
            )
        self.state.flow_states = states
