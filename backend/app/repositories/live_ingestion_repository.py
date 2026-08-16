from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.models.gps_ping import GPSPing
from app.models.live_ingestion import LiveIngestionBatch, SegmentCurrentState
from app.models.segment import Segment


class LiveIngestionRepository:
    """Database operations for one atomic live telemetry transaction."""

    def __init__(self, db: Session):
        self.db = db

    def segment_regions(self, segment_ids: set[str]) -> dict[str, str]:
        rows = self.db.query(Segment.segment_id, Segment.region_id).filter(Segment.segment_id.in_(segment_ids)).all()
        return {segment_id: region_id for segment_id, region_id in rows}

    def get_batch(self, source_id: str, run_id: str, batch_id: str) -> LiveIngestionBatch | None:
        return (
            self.db.query(LiveIngestionBatch)
            .filter_by(source_id=source_id, run_id=run_id, batch_id=batch_id)
            .one_or_none()
        )

    def persist_batch(
        self,
        batch_data: dict,
        observations: list[dict],
        states: list[dict],
    ) -> LiveIngestionBatch:
        receipt = LiveIngestionBatch(**batch_data)
        self.db.add(receipt)
        self.db.flush()

        self.db.bulk_save_objects([
            GPSPing(ingestion_batch_id=receipt.id, **observation)
            for observation in observations
        ])

        for state_data in states:
            current = self.db.get(SegmentCurrentState, state_data["segment_id"])
            if current is None:
                self.db.add(SegmentCurrentState(ingestion_batch_id=receipt.id, **state_data))
            elif state_data["last_updated"] >= current.last_updated:
                for key, value in state_data.items():
                    setattr(current, key, value)
                current.ingestion_batch_id = receipt.id

        self.db.commit()
        return receipt

    def rollback(self) -> None:
        self.db.rollback()

    def current_states(self, segment_ids: set[str] | None = None) -> list[SegmentCurrentState]:
        query = self.db.query(SegmentCurrentState)
        if segment_ids:
            query = query.filter(SegmentCurrentState.segment_id.in_(segment_ids))
        return query.order_by(SegmentCurrentState.segment_id.asc()).all()
