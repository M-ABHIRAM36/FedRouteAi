from sqlalchemy.orm import Session

from app.models.region import Region
from app.repositories.base_repository import BaseRepository


class RegionRepository(BaseRepository[Region]):
    def __init__(self, db: Session):
        super().__init__(db, Region)
