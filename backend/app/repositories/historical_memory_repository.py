from sqlalchemy.orm import Session

from app.models.historical_memory import HistoricalMemory
from app.repositories.base_repository import BaseRepository


class HistoricalMemoryRepository(BaseRepository[HistoricalMemory]):
    def __init__(self, db: Session):
        super().__init__(db, HistoricalMemory)

    def get_baseline(self, segment_id: str, hour_of_day: int) -> HistoricalMemory | None:
        return (
            self.db.query(HistoricalMemory)
            .filter(HistoricalMemory.segment_id == segment_id, HistoricalMemory.hour_of_day == hour_of_day)
            .first()
        )

    def get_baselines(self, keys: set[tuple[str, int]]) -> dict[tuple[str, int], HistoricalMemory]:
        if not keys:
            return {}
        segment_ids = {segment_id for segment_id, _ in keys}
        hours = {hour for _, hour in keys}
        rows = self.db.query(HistoricalMemory).filter(
            HistoricalMemory.segment_id.in_(segment_ids),
            HistoricalMemory.hour_of_day.in_(hours),
        ).all()
        return {(row.segment_id, row.hour_of_day): row for row in rows if (row.segment_id, row.hour_of_day) in keys}

    def upsert(self, profile) -> HistoricalMemory:
        """`profile` is a historical_memory.aggregator.HourlyProfile.
        Update-in-place if a row for this (segment, hour) exists,
        otherwise insert — this is what lets memory refresh over time
        instead of growing duplicate rows forever."""
        existing = self.get_baseline(profile.segment_id, profile.hour_of_day)
        if existing:
            existing.avg_speed_kmph = profile.avg_speed_kmph
            existing.std_speed_kmph = profile.std_speed_kmph
            existing.avg_vehicle_count = profile.avg_vehicle_count
            existing.uturn_rate = profile.uturn_rate
            existing.sample_size = profile.sample_size
            self.db.commit()
            self.db.refresh(existing)
            return existing

        row = HistoricalMemory(
            segment_id=profile.segment_id, hour_of_day=profile.hour_of_day,
            avg_speed_kmph=profile.avg_speed_kmph, std_speed_kmph=profile.std_speed_kmph,
            avg_vehicle_count=profile.avg_vehicle_count, uturn_rate=profile.uturn_rate,
            sample_size=profile.sample_size,
        )
        return self.add(row)

    def upsert_many(self, profiles: list) -> list[HistoricalMemory]:
        """Upsert a simulator tick's profiles in one transaction."""
        rows: list[HistoricalMemory] = []
        existing_by_key = self.get_baselines({(profile.segment_id, profile.hour_of_day) for profile in profiles})
        for profile in profiles:
            existing = existing_by_key.get((profile.segment_id, profile.hour_of_day))
            if existing is None:
                existing = HistoricalMemory(
                    segment_id=profile.segment_id,
                    hour_of_day=profile.hour_of_day,
                )
                self.db.add(existing)
                existing_by_key[(profile.segment_id, profile.hour_of_day)] = existing
            existing.avg_speed_kmph = profile.avg_speed_kmph
            existing.std_speed_kmph = profile.std_speed_kmph
            existing.avg_vehicle_count = profile.avg_vehicle_count
            existing.uturn_rate = profile.uturn_rate
            existing.sample_size = profile.sample_size
            rows.append(existing)
        self.db.commit()
        return rows
