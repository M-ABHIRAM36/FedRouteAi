"""Read-optimized queries for the normalized live map snapshot."""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session, aliased

from app.models.gps_ping import GPSPing
from app.models.live_ingestion import LiveIngestionBatch, SegmentCurrentState
from app.models.geo_v2 import LiveScenario, SegmentPrediction


class LiveMapRepository:
    def __init__(self, db: Session):
        self.db = db

    def latest_batch(self, source_id: str | None = None, run_id: str | None = None) -> LiveIngestionBatch | None:
        query = self.db.query(LiveIngestionBatch)
        if source_id:
            query = query.filter(LiveIngestionBatch.source_id == source_id)
        if run_id:
            query = query.filter(LiveIngestionBatch.run_id == run_id)
        return query.order_by(LiveIngestionBatch.received_at.desc(), LiveIngestionBatch.id.desc()).first()

    def latest_vehicle_positions(
        self,
        source_id: str,
        run_id: str,
        snapshot_at: datetime,
        fresh_after: datetime,
    ) -> list[GPSPing]:
        ranked = (
            self.db.query(
                GPSPing.id.label("ping_id"),
                func.row_number().over(
                    partition_by=GPSPing.vehicle_id,
                    order_by=(GPSPing.timestamp.desc(), GPSPing.id.desc()),
                ).label("position_rank"),
            )
            .join(LiveIngestionBatch, LiveIngestionBatch.id == GPSPing.ingestion_batch_id)
            .filter(
                LiveIngestionBatch.source_id == source_id,
                LiveIngestionBatch.run_id == run_id,
                GPSPing.timestamp <= snapshot_at,
                GPSPing.timestamp >= fresh_after,
            )
            .subquery()
        )
        latest = aliased(GPSPing)
        return (
            self.db.query(latest)
            .join(ranked, ranked.c.ping_id == latest.id)
            .filter(ranked.c.position_rank == 1)
            .order_by(latest.vehicle_id.asc())
            .all()
        )

    def segment_states(self, source_id: str, run_id: str) -> list[SegmentCurrentState]:
        return (
            self.db.query(SegmentCurrentState)
            .join(LiveIngestionBatch, LiveIngestionBatch.id == SegmentCurrentState.ingestion_batch_id)
            .filter(
                LiveIngestionBatch.source_id == source_id,
                LiveIngestionBatch.run_id == run_id,
            )
            .order_by(SegmentCurrentState.segment_id.asc())
            .all()
        )

    def latest_predictions(self, source_id: str, run_id: str) -> list[SegmentPrediction]:
        latest = self.db.query(
            SegmentPrediction.segment_id,
            func.max(SegmentPrediction.timestamp).label("timestamp"),
        ).filter(
            SegmentPrediction.source_id == source_id,
            SegmentPrediction.run_id == run_id,
        ).group_by(SegmentPrediction.segment_id).subquery()
        return self.db.query(SegmentPrediction).join(
            latest,
            (latest.c.segment_id == SegmentPrediction.segment_id)
            & (latest.c.timestamp == SegmentPrediction.timestamp),
        ).filter(
            SegmentPrediction.source_id == source_id,
            SegmentPrediction.run_id == run_id,
        ).all()

    def active_scenarios(self, source_id: str, run_id: str, at: datetime) -> list[LiveScenario]:
        return self.db.query(LiveScenario).filter(
            LiveScenario.source_id == source_id,
            LiveScenario.run_id == run_id,
            LiveScenario.start_time <= at,
            LiveScenario.end_time > at,
        ).order_by(LiveScenario.event_id).all()
