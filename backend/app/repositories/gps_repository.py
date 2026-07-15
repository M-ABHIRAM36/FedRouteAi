from datetime import timedelta

from sqlalchemy.orm import Session

from app.models.gps_ping import GPSPing
from app.repositories.base_repository import BaseRepository
from app.utils.time_utils import utcnow


class GPSPingRepository(BaseRepository[GPSPing]):
    def __init__(self, db: Session):
        super().__init__(db, GPSPing)

    def get_recent_for_segment(self, segment_id: str, since) -> list[GPSPing]:
        return (
            self.db.query(GPSPing)
            .filter(GPSPing.segment_id == segment_id, GPSPing.timestamp >= since)
            .order_by(GPSPing.timestamp.asc())
            .all()
        )

    def get_for_segment_hour_window(self, segment_id: str, hour_of_day: int, lookback_days: int = 14):
        """All pings for this segment that fall in this hour-of-day
        bucket, across the last `lookback_days` — this is what the
        historical memory builder aggregates into one baseline row.
        Filtered hour-of-day in Python rather than SQL to stay portable
        across the sqlite-in-tests / postgres-in-prod split this
        project relies on (see tests/conftest.py)."""
        since = utcnow() - timedelta(days=lookback_days)
        rows = self.db.query(GPSPing).filter(GPSPing.segment_id == segment_id, GPSPing.timestamp >= since).all()
        return [r for r in rows if r.timestamp.hour == hour_of_day]

    def bulk_insert(self, pings: list[GPSPing]) -> None:
        self.db.add_all(pings)
        self.db.commit()
