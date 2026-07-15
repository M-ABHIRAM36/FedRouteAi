from sqlalchemy.orm import Session

from app.models.fl_round_record import FLRoundRecord
from app.repositories.base_repository import BaseRepository


class FLRoundRepository(BaseRepository[FLRoundRecord]):
    def __init__(self, db: Session):
        super().__init__(db, FLRoundRecord)

    def get_latest_for_region(self, region_id: str) -> FLRoundRecord | None:
        return (
            self.db.query(FLRoundRecord)
            .filter(FLRoundRecord.region_id == region_id)
            .order_by(FLRoundRecord.round_number.desc())
            .first()
        )

    def record_round(self, **kwargs) -> FLRoundRecord:
        row = FLRoundRecord(**kwargs)
        return self.add(row)
