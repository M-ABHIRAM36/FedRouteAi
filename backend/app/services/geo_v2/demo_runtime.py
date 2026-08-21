"""Controlled, label-free Geo V2 demonstration orchestration."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from threading import RLock
from time import monotonic, perf_counter
from uuid import uuid4

from app.core.config import settings
from app.core.constants import EventType
from app.schemas.geo_v2_demo import DemoScenario, GeoV2DemoCreateIn, GeoV2DemoRunOut, GeoV2DemoStepOut
from app.schemas.geo_v2_inference import GeoV2InferenceItem
from app.schemas.gps_ping import LiveGPSBatchIn
from app.repositories.geo_v2_repository import GeoV2Repository
from app.repositories.historical_memory_repository import HistoricalMemoryRepository
from app.repositories.live_ingestion_repository import LiveIngestionRepository
from app.repositories.segment_repository import SegmentRepository
from app.services.geo_v2.prediction_service import GeoV2PredictionService
from app.services.geo_v2.runtime_inference import CausalFeatureContextCache
from app.services.geo_v2.simulation import GeoV2Simulation, SimulationConfig
from app.services.live_ingestion.service import ingest_live_batch


DEMO_SOURCE_ID = "geo-v2-demo"
DEMO_RUN_TTL_SECONDS = 60 * 60
MAX_DEMO_RUNS = 8


def scrub_demo_observations(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    """Remove scenario truth before telemetry enters the ingestion boundary."""
    return [{**row, "label": EventType.NORMAL.value, "event_id": ""} for row in rows]


@dataclass(slots=True)
class DemoRun:
    run_id: str
    scenario: DemoScenario
    simulation: GeoV2Simulation
    corridor: tuple[str, ...]
    disturbance_segment_id: str | None
    route_distance_m: float
    context_cache: CausalFeatureContextCache
    lock: RLock = field(default_factory=RLock)
    last_accessed_at: float = field(default_factory=monotonic)


class GeoV2DemoRegistry:
    def __init__(self) -> None:
        self._runs: dict[str, DemoRun] = {}
        self._lock = RLock()

    def create(self, request: GeoV2DemoCreateIn, network) -> DemoRun:
        simulation = GeoV2Simulation(network, SimulationConfig(
            vehicle_count=request.vehicle_count,
            tick_seconds=1,
            simulation_speed=120,
            random_seed=request.random_seed,
            start_time=datetime(2026, 8, 17, 8, 0),
            controlled_route_share=0.9,
            controlled_corridor_count=3,
            controlled_route_segment_ids=tuple(request.ordered_route_segment_ids),
        ))
        if not simulation.demo_corridors:
            raise ValueError("the persisted directed topology has no suitable demonstration corridor")
        corridor = simulation.demo_corridors[0]
        affected_segments: tuple[str, ...] = ()
        if request.scenario is DemoScenario.ACCIDENT:
            affected_segments = (corridor[len(corridor) // 2],)
        elif request.scenario is DemoScenario.CONGESTION:
            midpoint = len(corridor) // 2
            affected_segments = tuple(corridor[max(1, midpoint - 1):min(len(corridor) - 1, midpoint + 2)])
        disturbance = affected_segments[len(affected_segments) // 2] if affected_segments else None
        for index, affected_segment_id in enumerate(affected_segments):
            event_type = EventType.ACCIDENT if request.scenario is DemoScenario.ACCIDENT else EventType.CONGESTION
            simulation.schedule_event(
                event_type,
                affected_segment_id,
                start_time=simulation.config.start_time + timedelta(minutes=4),
                duration_minutes=20,
                severity=1.0 if event_type is EventType.ACCIDENT else 0.9,
                event_id=f"DEMO_DISTURBANCE_{index + 1}",
            )
        simulation.start()
        run = DemoRun(
            run_id=f"demo-{uuid4().hex[:12]}",
            scenario=request.scenario,
            simulation=simulation,
            corridor=corridor,
            disturbance_segment_id=disturbance,
            route_distance_m=request.route_distance_m,
            context_cache=CausalFeatureContextCache(),
        )
        with self._lock:
            self._remove_expired_locked()
            if len(self._runs) >= MAX_DEMO_RUNS:
                oldest_id = min(self._runs, key=lambda item: self._runs[item].last_accessed_at)
                self._runs.pop(oldest_id).simulation.stop()
            self._runs[run.run_id] = run
        return run

    def get(self, run_id: str) -> DemoRun:
        with self._lock:
            self._remove_expired_locked()
            run = self._runs.get(run_id)
            if run is not None:
                run.last_accessed_at = monotonic()
        if run is None:
            raise LookupError(f"demo run {run_id!r} is not active in this backend process")
        return run

    def remove(self, run_id: str) -> None:
        with self._lock:
            run = self._runs.pop(run_id, None)
        if run:
            with run.lock:
                run.simulation.stop()

    def _remove_expired_locked(self) -> None:
        cutoff = monotonic() - DEMO_RUN_TTL_SECONDS
        expired = [run_id for run_id, run in self._runs.items() if run.last_accessed_at < cutoff]
        for run_id in expired:
            self._runs.pop(run_id).simulation.stop()


DEMO_REGISTRY = GeoV2DemoRegistry()


def demo_run_status(run: DemoRun) -> GeoV2DemoRunOut:
    return GeoV2DemoRunOut(
        source_id=DEMO_SOURCE_ID,
        run_id=run.run_id,
        scenario=run.scenario,
        status="ready" if run.simulation.state.running else "stopped",
        simulation_time=run.simulation.state.current_time,
        tick_number=run.simulation.state.tick_number,
        vehicle_count=len(run.simulation.state.vehicles),
        network_source=settings.GEO_V2_NETWORK_SOURCE,
        network_version=settings.GEO_V2_NETWORK_VERSION,
        corridor_segment_ids=list(run.corridor),
        route_distance_m=run.route_distance_m,
        disturbance_segment_id=run.disturbance_segment_id,
    )


def step_demo_run(run: DemoRun, ingestion_repository, segments, baselines, predictions) -> GeoV2DemoStepOut:
    with run.lock:
        run.last_accessed_at = monotonic()
        return _step_demo_run_locked(run, ingestion_repository, segments, baselines, predictions)


def _step_demo_run_locked(run: DemoRun, ingestion_repository, segments, baselines, predictions) -> GeoV2DemoStepOut:
    raw_observations = run.simulation.tick()
    clean_observations = scrub_demo_observations(raw_observations)
    batch = LiveGPSBatchIn.model_validate({
        "source_id": DEMO_SOURCE_ID,
        "run_id": run.run_id,
        "batch_id": f"tick-{run.simulation.state.tick_number:08d}",
        "tick_number": run.simulation.state.tick_number,
        "network_source": settings.GEO_V2_NETWORK_SOURCE,
        "network_version": settings.GEO_V2_NETWORK_VERSION,
        "observations": clean_observations,
    })
    ingestion_started = perf_counter()
    receipt = ingest_live_batch(batch, ingestion_repository)
    ingestion_ms = (perf_counter() - ingestion_started) * 1000

    outgoing: dict[str, set[str]] = defaultdict(set)
    for transition in run.simulation.network.transitions:
        outgoing[transition.from_segment_id].add(transition.to_segment_id)
    observed_states = {
        segment_id: state
        for segment_id, state in run.simulation.state.flow_states.items()
        if state.vehicle_count > 0
    }
    items = []
    for segment_id, state in observed_states.items():
        neighbors = [
            observed_states[neighbor_id]
            for neighbor_id in sorted(outgoing.get(segment_id, ()))
            if neighbor_id in observed_states
        ]
        items.append(GeoV2InferenceItem.model_validate({
            "source_id": DEMO_SOURCE_ID,
            "run_id": run.run_id,
            "segment_id": segment_id,
            "as_of": run.simulation.state.current_time,
            "telemetry": _telemetry(state),
            "neighbors": [{"segment_id": item.segment_id, **_telemetry(item)} for item in neighbors],
        }))
    inference_started = perf_counter()
    results = GeoV2PredictionService(
        segments, baselines, predictions, cache=run.context_cache,
    ).infer_batch(items)
    inference_ms = (perf_counter() - inference_started) * 1000
    status = demo_run_status(run).model_dump()
    return GeoV2DemoStepOut(
        **status,
        accepted_observations=receipt.accepted,
        observed_segments=len(items),
        predictions_available=sum(result.status == "ok" for _, _, result in results),
        ingestion_ms=round(ingestion_ms, 2),
        inference_ms=round(inference_ms, 2),
    )


class GeoV2DemoService:
    """Application boundary for demo lifecycle and persistence collaborators."""

    def __init__(self, network_repository, ingestion_repository, segment_repository, baseline_repository) -> None:
        self.network_repository = network_repository
        self.ingestion_repository = ingestion_repository
        self.segment_repository = segment_repository
        self.baseline_repository = baseline_repository

    def create(self, request: GeoV2DemoCreateIn) -> GeoV2DemoRunOut:
        from app.ml.geo_v2.model_store import GEO_V2_MODEL_STORE

        if GEO_V2_MODEL_STORE.network_version != settings.GEO_V2_NETWORK_VERSION:
            raise ValueError("Geo V2 model and configured network versions do not match")
        network = self.network_repository.load_network(
            settings.GEO_V2_NETWORK_VERSION, settings.GEO_V2_NETWORK_SOURCE,
        )
        if not network.segments:
            raise ValueError("configured Geo V2 network is not imported")
        return demo_run_status(DEMO_REGISTRY.create(request, network))

    def status(self, run_id: str) -> GeoV2DemoRunOut:
        return demo_run_status(DEMO_REGISTRY.get(run_id))

    def step(self, run_id: str) -> GeoV2DemoStepOut:
        return step_demo_run(
            DEMO_REGISTRY.get(run_id), self.ingestion_repository,
            self.segment_repository, self.baseline_repository, self.network_repository,
        )

    def stop(self, run_id: str) -> None:
        DEMO_REGISTRY.remove(run_id)


def build_geo_v2_demo_service(db) -> GeoV2DemoService:
    return GeoV2DemoService(
        GeoV2Repository(db), LiveIngestionRepository(db),
        SegmentRepository(db), HistoricalMemoryRepository(db),
    )


def _telemetry(state) -> dict[str, float | int]:
    return {
        "avg_speed_kmph": state.average_speed_kmph,
        "speed_std_kmph": state.speed_variance ** 0.5,
        "vehicle_count": state.vehicle_count,
        "occupancy": state.occupancy,
        "flow_rate_vph": state.flow_rate_vph,
        "stopped_fraction": 1.0 if state.average_speed_kmph < 1.0 else 0.0,
    }
