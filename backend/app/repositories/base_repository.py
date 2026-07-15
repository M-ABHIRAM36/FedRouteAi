"""Generic CRUD so per-entity repositories don't repeat boilerplate.
Repositories are the ONLY layer allowed to import sqlalchemy Session
queries directly — services must go through a repository, never touch
the DB session themselves. Keeps business logic testable without a DB."""
from typing import Generic, TypeVar

from sqlalchemy.orm import Session

ModelT = TypeVar("ModelT")


class BaseRepository(Generic[ModelT]):
    def __init__(self, db: Session, model: type[ModelT]):
        self.db = db
        self.model = model

    def get(self, pk) -> ModelT | None:
        return self.db.get(self.model, pk)

    def list_all(self, limit: int = 100, offset: int = 0) -> list[ModelT]:
        return self.db.query(self.model).offset(offset).limit(limit).all()

    def add(self, obj: ModelT) -> ModelT:
        self.db.add(obj)
        self.db.commit()
        self.db.refresh(obj)
        return obj

    def add_all(self, objs: list[ModelT]) -> None:
        self.db.add_all(objs)
        self.db.commit()
