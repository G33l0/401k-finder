from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from app.core.config import get_database_path

_engine: Engine | None = None


def _configure_connection(dbapi_connection, _record) -> None:  # noqa: ANN001
    """
    Apply per-connection SQLite settings.

    Pragmas set on one connection do not carry to the next, so foreign keys and
    the cache configuration have to be re-applied every time the pool opens one.
    """

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute("PRAGMA journal_mode = WAL")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA temp_store = MEMORY")
        cursor.execute("PRAGMA cache_size = -262144")
        cursor.execute("PRAGMA busy_timeout = 30000")
    finally:
        cursor.close()


def create_database_engine(path: Path | None = None, echo: bool = False) -> Engine:
    """
    Create a SQLite engine for the local plan database.

    SQLite is the right fit here: the data is a single-user local cache of
    public files, it needs no server, and the whole database is one file the
    user can copy or delete.
    """

    database_path = path or get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    engine = create_engine(
        f"sqlite:///{database_path}",
        echo=echo,
        future=True,
        # The Qt worker threads each take their own session from the pool.
        connect_args={"check_same_thread": False, "timeout": 30.0},
    )

    event.listen(engine, "connect", _configure_connection)
    return engine


def get_engine() -> Engine:
    """Return the process-wide engine, creating it on first use."""

    global _engine

    if _engine is None:
        _engine = create_database_engine()

    return _engine


def set_engine(engine: Engine) -> None:
    """Replace the process-wide engine. Used by the test suite and the CLI."""

    global _engine
    _engine = engine


def dispose_engine() -> None:
    """Close all pooled connections, releasing the database file."""

    global _engine

    if _engine is not None:
        _engine.dispose()
        _engine = None
