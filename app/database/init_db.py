from __future__ import annotations

from sqlalchemy import text

from app.database.base import Base
from app.database.engine import engine

# Import models so SQLAlchemy knows every table.
from app.database import models  # noqa: F401


def initialize_database() -> None:
    """Create all database tables if they do not already exist."""
    Base.metadata.create_all(bind=engine)

    with engine.begin() as connection:
        connection.execute(
            text("PRAGMA foreign_keys = ON")
        )


if __name__ == "__main__":
    initialize_database()
    print("Database initialized successfully.")