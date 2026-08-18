from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine

from app.core.config import get_database_path
from app.core.logging import get_logger

logger = get_logger(__name__)

_engine: Engine | None = None


def journal_mode_for(path: Path) -> str:
    """The journal mode that will actually work where the database lives."""

    from app.core import storage

    try:
        _, _, network = storage.volume_details(path.parent)
    except Exception:  # noqa: BLE001 - detection is advisory
        return "WAL"

    if network:
        logger.info(
            "Database is on a network location; using the rollback journal "
            "because the write-ahead log needs shared memory that network "
            "shares do not provide."
        )
        return "DELETE"

    return "WAL"


def _configure_connection(dbapi_connection, _record) -> None:  # noqa: ANN001
    """Apply per-connection SQLite settings."""

    cursor = dbapi_connection.cursor()
    try:
        cursor.execute("PRAGMA foreign_keys = ON")
        cursor.execute(f"PRAGMA journal_mode = {_JOURNAL_MODE}")
        cursor.execute("PRAGMA synchronous = NORMAL")
        cursor.execute("PRAGMA temp_store = MEMORY")
        cursor.execute("PRAGMA cache_size = -262144")
        cursor.execute("PRAGMA busy_timeout = 60000")
    finally:
        cursor.close()


# Resolved once per engine: the pool opens connections on worker threads,
# where a filesystem probe per query would be wasteful.
_JOURNAL_MODE = "WAL"


def create_database_engine(path: Path | None = None, echo: bool = False) -> Engine:
    """Create a SQLite engine for the local plan database."""

    global _JOURNAL_MODE

    database_path = path or get_database_path()
    database_path.parent.mkdir(parents=True, exist_ok=True)

    _JOURNAL_MODE = journal_mode_for(database_path)

    engine = create_engine(
        f"sqlite:///{database_path}",
        echo=echo,
        future=True,
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


def current_journal_mode() -> str:
    """The journal mode in force for the engine most recently created."""

    return _JOURNAL_MODE
