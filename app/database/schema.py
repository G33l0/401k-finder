"""Versioned schema management for the local SQLite database."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine

from app.core.exceptions import DatabaseError
from app.core.logging import get_logger
from app.database import models  # noqa: F401
from app.database.base import Base

logger = get_logger(__name__)

SCHEMA_VERSION = 5

FTS_TABLE = "plan_fts"


@dataclass(frozen=True, slots=True)
class MigrationStep:
    version: int
    description: str
    apply: Callable[[Connection], None]


def _apply_pragmas(connection: Connection) -> None:
    """Configure SQLite for a large local analytical cache."""

    from app.database.engine import current_journal_mode

    for pragma in (
        f"PRAGMA journal_mode = {current_journal_mode()}",
        "PRAGMA synchronous = NORMAL",
        "PRAGMA foreign_keys = ON",
        "PRAGMA temp_store = MEMORY",
        "PRAGMA cache_size = -262144",  # ~256 MB
        "PRAGMA mmap_size = 268435456",
    ):
        connection.exec_driver_sql(pragma)


def _create_fts(connection: Connection) -> None:
    """Create the FTS5 index over plan identity and keep it in step with `plans`."""

    connection.exec_driver_sql(
        f"""
        CREATE VIRTUAL TABLE IF NOT EXISTS {FTS_TABLE} USING fts5(
            plan_name,
            sponsor_name,
            sponsor_dba_name,
            ein UNINDEXED,
            plan_number UNINDEXED,
            sponsor_city,
            sponsor_state,
            plan_id UNINDEXED,
            tokenize = "unicode61 remove_diacritics 2"
        )
        """
    )

    connection.exec_driver_sql(
        """
        CREATE VIRTUAL TABLE IF NOT EXISTS provider_fts USING fts5(
            name,
            canonical_name,
            provider_id UNINDEXED,
            tokenize = "unicode61 remove_diacritics 2"
        )
        """
    )


def _supports_fts5(connection: Connection) -> bool:
    try:
        connection.exec_driver_sql("CREATE VIRTUAL TABLE temp.__fts_probe USING fts5(x)")
        connection.exec_driver_sql("DROP TABLE temp.__fts_probe")
        return True
    except Exception:  # noqa: BLE001 - any failure means the module is unavailable
        return False


def _step_initial(connection: Connection) -> None:
    Base.metadata.create_all(bind=connection)


def _step_fts(connection: Connection) -> None:
    if _supports_fts5(connection):
        _create_fts(connection)
    else:
        logger.warning(
            "SQLite was built without FTS5; falling back to LIKE-based search. "
            "Searches will still work but will be slower on large databases."
        )


def _step_indexes(connection: Connection) -> None:
    """Indexes that back the search filters but are not expressed on the ORM."""

    for statement in (
        "CREATE INDEX IF NOT EXISTS ix_plan_name_nocase ON plans (plan_name COLLATE NOCASE)",
        "CREATE INDEX IF NOT EXISTS ix_plan_sponsor_nocase ON plans (sponsor_name COLLATE NOCASE)",
        "CREATE INDEX IF NOT EXISTS ix_provider_name_nocase ON providers (name COLLATE NOCASE)",
        "CREATE INDEX IF NOT EXISTS ix_party_role_year ON plan_parties (role, form_year)",
    ):
        connection.exec_driver_sql(statement)


def _step_evidence_uniqueness(connection: Connection) -> None:
    """Make evidence rows unique per source field."""

    connection.exec_driver_sql(
        """
        DELETE FROM evidence
        WHERE id NOT IN (
            SELECT MIN(id) FROM evidence
            GROUP BY ack_id, dataset, source_row, field_name
        )
        """
    )
    connection.exec_driver_sql(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_evidence_source_field
        ON evidence (ack_id, dataset, source_row, field_name)
        """
    )
    connection.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_evidence_plan_year ON evidence (plan_id, form_year)"
    )


def _step_plan_transfers(connection: Connection) -> None:
    """Record where a wound-up plan's assets went."""

    Base.metadata.tables["plan_transfers"].create(bind=connection, checkfirst=True)


MIGRATIONS: tuple[MigrationStep, ...] = (
    MigrationStep(1, "Create base tables", _step_initial),
    MigrationStep(2, "Create full-text search indexes", _step_fts),
    MigrationStep(3, "Create search support indexes", _step_indexes),
    MigrationStep(4, "Deduplicate evidence and enforce uniqueness", _step_evidence_uniqueness),
    MigrationStep(5, "Record plan-to-plan asset transfers", _step_plan_transfers),
)


def _read_version(connection: Connection) -> int:
    connection.exec_driver_sql(
        "CREATE TABLE IF NOT EXISTS schema_version ("
        " version INTEGER NOT NULL,"
        " applied_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP)"
    )
    row = connection.exec_driver_sql(
        "SELECT MAX(version) FROM schema_version"
    ).scalar()
    return int(row or 0)


def _write_version(connection: Connection, version: int) -> None:
    connection.exec_driver_sql(
        "INSERT INTO schema_version (version) VALUES (?)", (version,)
    )


def current_version(engine: Engine) -> int:
    """Return the schema version stored in the database, 0 if brand new."""

    with engine.begin() as connection:
        return _read_version(connection)


def initialize_database(engine: Engine) -> int:
    """Bring the database up to ``SCHEMA_VERSION``, creating it if needed."""

    with engine.begin() as connection:
        _apply_pragmas(connection)
        version = _read_version(connection)

        if version > SCHEMA_VERSION:
            raise DatabaseError(
                f"The database was written by a newer version of this application "
                f"(schema {version}, this build understands {SCHEMA_VERSION}). "
                f"Upgrade the application, or delete the database file to rebuild it."
            )

        for step in MIGRATIONS:
            if step.version <= version:
                continue

            logger.info("Applying schema step %s: %s", step.version, step.description)
            try:
                step.apply(connection)
            except Exception as exc:  # noqa: BLE001
                raise DatabaseError(
                    f"Schema step {step.version} ({step.description}) failed: {exc}"
                ) from exc

            _write_version(connection, step.version)
            version = step.version

    return version


def has_fts(engine: Engine) -> bool:
    """Return whether the full-text tables are present and usable."""

    with engine.connect() as connection:
        row = connection.exec_driver_sql(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (FTS_TABLE,),
        ).fetchone()
        return row is not None


def rebuild_fts(engine: Engine) -> int:
    """Repopulate the full-text indexes from `plans` and `providers`."""

    if not has_fts(engine):
        return 0

    with engine.begin() as connection:
        connection.exec_driver_sql(f"DELETE FROM {FTS_TABLE}")
        connection.exec_driver_sql(
            f"""
            INSERT INTO {FTS_TABLE} (
                plan_name, sponsor_name, sponsor_dba_name, ein,
                plan_number, sponsor_city, sponsor_state, plan_id
            )
            SELECT
                COALESCE(plan_name, ''), COALESCE(sponsor_name, ''),
                COALESCE(sponsor_dba_name, ''), COALESCE(ein, ''),
                COALESCE(plan_number, ''), COALESCE(sponsor_city, ''),
                COALESCE(sponsor_state, ''), id
            FROM plans
            """
        )

        connection.exec_driver_sql("DELETE FROM provider_fts")
        connection.exec_driver_sql(
            """
            INSERT INTO provider_fts (name, canonical_name, provider_id)
            SELECT COALESCE(name, ''), COALESCE(canonical_name, ''), id
            FROM providers
            """
        )

        return int(
            connection.exec_driver_sql(f"SELECT COUNT(*) FROM {FTS_TABLE}").scalar() or 0
        )


def analyze(engine: Engine) -> None:
    """Refresh SQLite's query planner statistics after a bulk import."""

    with engine.begin() as connection:
        connection.exec_driver_sql("ANALYZE")


def vacuum(engine: Engine) -> None:
    """Compact the database file. Requires exclusive access."""

    with engine.connect() as connection:
        connection.execute(text("COMMIT"))
        connection.exec_driver_sql("VACUUM")
