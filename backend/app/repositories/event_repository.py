from sqlalchemy.orm import Session

from app.models.event import Event
from app.repositories.base_repository import BaseRepository


class EventRepository(BaseRepository[Event]):
    def __init__(self, db: Session):
        super().__init__(db, Event)

    def get_active_for_segment(self, segment_id: str) -> list[Event]:
        return (
            self.db.query(Event)
            .filter(Event.primary_segment_id == segment_id, Event.source == "detected")
            .all()
        )

    def get_active_all(self) -> list[Event]:
        """All currently-open detected events — used by the routing
        service to reprice the graph before every path query."""
        return self.db.query(Event).filter(Event.source == "detected").all()
