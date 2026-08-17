"""Persistence boundary for canonical Geo V2 networks and live metadata."""
from __future__ import annotations

import json
from datetime import datetime

from geoalchemy2.elements import WKTElement
from sqlalchemy import delete, func
from sqlalchemy.orm import Session

from app.models.geo_v2 import GeoSegmentMetadata, GeoSegmentTransition, LiveScenario, SegmentPrediction
from app.models.region import Region
from app.models.segment import Segment
from app.services.geo_v2.network import CanonicalNetwork, CanonicalSegment, CanonicalTransition


class GeoV2Repository:
    def __init__(self, db: Session):
        self.db = db

    def replace_network(
        self,
        network: CanonicalNetwork,
        *,
        network_version: str,
        network_source: str = "osm_geo_v2",
        imported_at: datetime,
    ) -> None:
        if not network.segments:
            raise ValueError("cannot import an empty network")

        region_segments: dict[str, list[CanonicalSegment]] = {}
        for segment in network.segments:
            region_segments.setdefault(segment.region_id, []).append(segment)
        for region_id, segments in region_segments.items():
            center_lon = sum(_midpoint(item)[0] for item in segments) / len(segments)
            center_lat = sum(_midpoint(item)[1] for item in segments) / len(segments)
            region = self.db.get(Region, region_id)
            if region is None:
                region = Region(
                    region_id=region_id,
                    pincode=502032,
                    center_lat=center_lat,
                    center_lon=center_lon,
                    segment_count=len(segments),
                )
                self.db.add(region)
        self.db.flush()

        prior_ids = {
            row[0] for row in self.db.query(GeoSegmentMetadata.segment_id)
            .filter(GeoSegmentMetadata.network_version == network_version).all()
        }
        incoming_ids = {segment.segment_id for segment in network.segments}
        if prior_ids - incoming_ids:
            raise ValueError("network version already exists with different segment identities")

        outgoing: dict[str, list[str]] = {}
        for transition in network.transitions:
            outgoing.setdefault(transition.from_segment_id, []).append(transition.to_segment_id)

        for item in network.segments:
            segment = self.db.get(Segment, item.segment_id)
            if segment is None:
                segment = Segment(segment_id=item.segment_id)
                self.db.add(segment)
            segment.road_name = item.road_name
            segment.road_type = item.road_type.value
            segment.region_id = item.region_id
            segment.pincode = 502032
            segment.start_lon, segment.start_lat = item.geometry[0]
            segment.end_lon, segment.end_lat = item.geometry[-1]
            segment.segment_length_m = item.length_m
            segment.number_of_lanes = item.lanes
            segment.road_width_m = max(item.lanes * 3.25, 3.0)
            segment.max_speed_kmph = item.max_speed_kmph
            segment.road_direction = item.road_direction.value
            segment.flood_prone = False
            segment.neighbor_segments = ";".join(sorted(set(outgoing.get(item.segment_id, ()))))

        # No ORM relationship joins these additive tables, so enforce the FK
        # insertion order explicitly for PostgreSQL's immediate constraints.
        self.db.flush()

        for item in network.segments:
            geometry = self.db.get(GeoSegmentMetadata, item.segment_id)
            if geometry is None:
                geometry = GeoSegmentMetadata(segment_id=item.segment_id)
                self.db.add(geometry)
            geometry.network_source = network_source
            geometry.network_version = network_version
            geometry.osm_way_id = item.osm_way_id
            geometry.start_node_id = item.start_node_id
            geometry.end_node_id = item.end_node_id
            geometry.highway = item.highway
            geometry.geometry = _geometry_value(self.db, item.geometry)
            geometry.bridge = item.bridge
            geometry.tunnel = item.tunnel
            geometry.junction = item.junction
            geometry.imported_at = imported_at

        self.db.flush()
        self.db.execute(
            delete(GeoSegmentTransition).where(GeoSegmentTransition.network_version == network_version)
        )
        self.db.add_all([
            GeoSegmentTransition(
                from_segment_id=item.from_segment_id,
                to_segment_id=item.to_segment_id,
                via_node_id=item.via_node_id,
                network_version=network_version,
            )
            for item in network.transitions
        ])
        self.db.commit()

    def load_network(self, network_version: str) -> CanonicalNetwork:
        rows = (
            self.db.query(Segment, GeoSegmentMetadata)
            .join(GeoSegmentMetadata, GeoSegmentMetadata.segment_id == Segment.segment_id)
            .filter(GeoSegmentMetadata.network_version == network_version)
            .order_by(Segment.segment_id)
            .all()
        )
        segments = tuple(_canonical_segment(self.db, segment, metadata) for segment, metadata in rows)
        transitions = tuple(
            CanonicalTransition(row.from_segment_id, row.to_segment_id, row.via_node_id)
            for row in self.db.query(GeoSegmentTransition)
            .filter(GeoSegmentTransition.network_version == network_version)
            .order_by(
                GeoSegmentTransition.from_segment_id,
                GeoSegmentTransition.to_segment_id,
                GeoSegmentTransition.via_node_id,
            ).all()
        )
        points = [point for segment in segments for point in segment.geometry]
        bbox = (
            min(point[0] for point in points), min(point[1] for point in points),
            max(point[0] for point in points), max(point[1] for point in points),
        ) if points else (0.0, 0.0, 0.0, 0.0)
        return CanonicalNetwork(segments, transitions, bbox)

    def list_segments(self, network_source: str) -> list[tuple[Segment, GeoSegmentMetadata]]:
        return (
            self.db.query(Segment, GeoSegmentMetadata)
            .join(GeoSegmentMetadata, GeoSegmentMetadata.segment_id == Segment.segment_id)
            .filter(GeoSegmentMetadata.network_source == network_source)
            .order_by(Segment.segment_id).all()
        )

    def geometry_coordinates(self, metadata: GeoSegmentMetadata) -> tuple[tuple[float, float], ...]:
        return _coordinates(self.db, metadata)

    def active_scenarios(self, source_id: str, run_id: str, at: datetime) -> list[LiveScenario]:
        return self.db.query(LiveScenario).filter(
            LiveScenario.source_id == source_id,
            LiveScenario.run_id == run_id,
            LiveScenario.start_time <= at,
            LiveScenario.end_time > at,
        ).order_by(LiveScenario.event_id).all()

    def save_scenarios(self, rows: list[dict]) -> list[LiveScenario]:
        scenarios = [LiveScenario(**row) for row in rows]
        self.db.add_all(scenarios)
        self.db.commit()
        return scenarios

    def scenario_count(self) -> int:
        return self.db.query(LiveScenario).count()

    def segment_regions(self, segment_ids: set[str]) -> dict[str, str]:
        return dict(self.db.query(Segment.segment_id, Segment.region_id).filter(Segment.segment_id.in_(segment_ids)).all())

    def transitions_for_segments(self, segment_ids: set[str]) -> list[CanonicalTransition]:
        return [
            CanonicalTransition(row.from_segment_id, row.to_segment_id, row.via_node_id)
            for row in self.db.query(GeoSegmentTransition).filter(
                (GeoSegmentTransition.from_segment_id.in_(segment_ids))
                | (GeoSegmentTransition.to_segment_id.in_(segment_ids))
            ).all()
        ]

    def outgoing_neighbors(self, segment_ids: set[str], network_version: str) -> dict[str, set[str]]:
        rows = self.db.query(
            GeoSegmentTransition.from_segment_id, GeoSegmentTransition.to_segment_id,
        ).filter(
            GeoSegmentTransition.network_version == network_version,
            GeoSegmentTransition.from_segment_id.in_(segment_ids),
        ).all()
        result = {segment_id: set() for segment_id in segment_ids}
        for source, target in rows:
            result[source].add(target)
        return result

    def save_prediction(self, values: dict) -> SegmentPrediction:
        existing = self.db.query(SegmentPrediction).filter_by(
            source_id=values["source_id"], run_id=values["run_id"],
            segment_id=values["segment_id"], timestamp=values["timestamp"],
            model_version=values["model_version"],
        ).one_or_none()
        if existing is None:
            existing = SegmentPrediction(**values)
            self.db.add(existing)
        else:
            for key, value in values.items():
                setattr(existing, key, value)
        self.db.commit()
        return existing

    def save_predictions(self, rows: list[dict]) -> list[SegmentPrediction]:
        """Persist a tick's predictions idempotently in one transaction."""
        predictions: list[SegmentPrediction] = []
        grouped: dict[tuple[str, str, datetime, str], set[str]] = {}
        for values in rows:
            key = (values["source_id"], values["run_id"], values["timestamp"], values["model_version"])
            grouped.setdefault(key, set()).add(values["segment_id"])
        existing_by_key = {}
        for (source_id, run_id, timestamp, model_version), segment_ids in grouped.items():
            existing_rows = self.db.query(SegmentPrediction).filter(
                SegmentPrediction.source_id == source_id,
                SegmentPrediction.run_id == run_id,
                SegmentPrediction.timestamp == timestamp,
                SegmentPrediction.model_version == model_version,
                SegmentPrediction.segment_id.in_(segment_ids),
            ).all()
            existing_by_key.update({
                (row.source_id, row.run_id, row.segment_id, row.timestamp, row.model_version): row
                for row in existing_rows
            })
        for values in rows:
            key = (
                values["source_id"], values["run_id"], values["segment_id"],
                values["timestamp"], values["model_version"],
            )
            existing = existing_by_key.get(key)
            if existing is None:
                existing = SegmentPrediction(**values)
                self.db.add(existing)
                existing_by_key[key] = existing
            else:
                for key, value in values.items():
                    setattr(existing, key, value)
            predictions.append(existing)
        self.db.commit()
        return predictions

    def latest_predictions(self, source_id: str, run_id: str) -> list[SegmentPrediction]:
        latest = self.db.query(
            SegmentPrediction.segment_id,
            func.max(SegmentPrediction.timestamp).label("timestamp"),
        ).filter_by(source_id=source_id, run_id=run_id).group_by(SegmentPrediction.segment_id).subquery()
        return self.db.query(SegmentPrediction).join(
            latest,
            (latest.c.segment_id == SegmentPrediction.segment_id)
            & (latest.c.timestamp == SegmentPrediction.timestamp),
        ).filter_by(source_id=source_id, run_id=run_id).all()

    def prediction_history(
        self, source_id: str, run_id: str, segment_id: str, before: datetime, limit: int = 3,
    ) -> list[SegmentPrediction]:
        return self.db.query(SegmentPrediction).filter(
            SegmentPrediction.source_id == source_id,
            SegmentPrediction.run_id == run_id,
            SegmentPrediction.segment_id == segment_id,
            SegmentPrediction.timestamp < before,
        ).order_by(SegmentPrediction.timestamp.desc()).limit(limit).all()

    def prediction_histories(
        self, source_id: str, run_id: str, segment_ids: set[str], before: datetime, limit: int = 3,
    ) -> dict[str, list[SegmentPrediction]]:
        if not segment_ids:
            return {}
        ranked = self.db.query(
            SegmentPrediction.id.label("prediction_id"),
            func.row_number().over(
                partition_by=SegmentPrediction.segment_id,
                order_by=SegmentPrediction.timestamp.desc(),
            ).label("history_rank"),
        ).filter(
            SegmentPrediction.source_id == source_id,
            SegmentPrediction.run_id == run_id,
            SegmentPrediction.segment_id.in_(segment_ids),
            SegmentPrediction.timestamp < before,
        ).subquery()
        rows = self.db.query(SegmentPrediction).join(
            ranked, ranked.c.prediction_id == SegmentPrediction.id,
        ).filter(ranked.c.history_rank <= limit).order_by(
            SegmentPrediction.segment_id, SegmentPrediction.timestamp.desc(),
        ).all()
        histories: dict[str, list[SegmentPrediction]] = {}
        for row in rows:
            histories.setdefault(row.segment_id, []).append(row)
        return histories


def _midpoint(segment: CanonicalSegment) -> tuple[float, float]:
    return segment.geometry[len(segment.geometry) // 2]


def _geometry_value(db: Session, coordinates: tuple[tuple[float, float], ...]):
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        points = ",".join(f"{lon} {lat}" for lon, lat in coordinates)
        return WKTElement(f"LINESTRING({points})", srid=4326)
    return json.dumps({"type": "LineString", "coordinates": coordinates}, separators=(",", ":"))


def _coordinates(db: Session, metadata: GeoSegmentMetadata) -> tuple[tuple[float, float], ...]:
    if db.bind is not None and db.bind.dialect.name == "postgresql":
        value = db.query(func.ST_AsGeoJSON(GeoSegmentMetadata.geometry)).filter_by(segment_id=metadata.segment_id).scalar()
    else:
        value = metadata.geometry
    payload = json.loads(value)
    return tuple((float(point[0]), float(point[1])) for point in payload["coordinates"])


def _canonical_segment(db: Session, segment: Segment, metadata: GeoSegmentMetadata) -> CanonicalSegment:
    from app.core.constants import RoadDirection, RoadType

    return CanonicalSegment(
        segment_id=segment.segment_id, osm_way_id=metadata.osm_way_id,
        start_node_id=metadata.start_node_id, end_node_id=metadata.end_node_id,
        geometry=_coordinates(db, metadata), road_name=segment.road_name, highway=metadata.highway,
        road_type=RoadType(segment.road_type), region_id=segment.region_id,
        length_m=segment.segment_length_m, max_speed_kmph=segment.max_speed_kmph,
        lanes=segment.number_of_lanes, one_way=segment.road_direction == RoadDirection.ONE_WAY.value,
        is_reversed=False, road_direction=RoadDirection(segment.road_direction), bridge=metadata.bridge,
        tunnel=metadata.tunnel, junction=metadata.junction,
    )
