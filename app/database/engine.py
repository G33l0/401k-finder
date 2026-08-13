from __future__ import annotations

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from app.core.config import DATABASE_PATH


def create_database_engine() -> Engine:
    """
    Create the SQLite database engine.

    SQLite is intentionally used for the desktop application because
    the database is local and portable.
    """
    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)

    return create_engine(
        f"sqlite:///{DATABASE_PATH}",
        connect_args={"check_same_thread": False},
        future=True,
    )


engine = create_database_engine()