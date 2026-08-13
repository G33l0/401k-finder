from __future__ import annotations

from sqlalchemy import text

from app.database.base import Base
from app.database.engine import engine

# Importing models registers every ORM class with Base.metadata.
from app.database import models  # noqa: F401


def initialize_database() -> None:
    """Create the application database tables if they do not exist."""

    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(text("PRAGMA foreign_keys = ON"))
        connection.execute(text("PRAGMA journal_mode = WAL"))
        connection.execute(text("PRAGMA synchronous = NORMAL"))


if __name__ == "__main__":
    initialize_database()
    print("Database initialized successfully.")