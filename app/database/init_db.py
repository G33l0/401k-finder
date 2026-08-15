from __future__ import annotations

from pathlib import Path

from sqlalchemy.engine import Engine

from app.core.logging import get_logger
from app.database.engine import get_engine
from app.database.schema import (
    SCHEMA_VERSION,
    analyze,
    current_version,
    has_fts,
    rebuild_fts,
)
from app.database.schema import (
    initialize_database as _initialize,
)

logger = get_logger(__name__)

__all__ = (
    "SCHEMA_VERSION",
    "analyze",
    "current_version",
    "has_fts",
    "initialize_database",
    "rebuild_fts",
    "reset_database",
)


def initialize_database(engine: Engine | None = None) -> int:
    """Create or upgrade the local database and return its schema version."""

    target = engine or get_engine()
    version = _initialize(target)
    logger.info("Database ready at schema version %s", version)
    return version


def reset_database(path: Path | None = None) -> None:
    """
    Delete the database file and rebuild it empty.

    The database is a cache of public DOL files, so discarding it loses no
    original data — but it does discard every import, so callers should confirm
    with the user first.
    """

    from app.core.config import get_database_path
    from app.database.engine import dispose_engine
    from app.database.session import reset_session_factory

    target = path or get_database_path()

    dispose_engine()
    reset_session_factory()

    for suffix in ("", "-wal", "-shm"):
        candidate = Path(str(target) + suffix)
        if candidate.exists():
            candidate.unlink()

    logger.info("Database removed: %s", target)
    initialize_database()


if __name__ == "__main__":
    version = initialize_database()
    print(f"Database initialized at schema version {version}.")
