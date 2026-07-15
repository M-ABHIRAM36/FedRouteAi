"""SQLAlchemy declarative base. Every ORM model in app/models/ inherits
from `Base` so Alembic can autogenerate migrations from one place."""
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
