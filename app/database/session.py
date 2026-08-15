from __future__ import annotations

from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy.orm import Session, sessionmaker

from app.database.engine import get_engine

_factory: sessionmaker[Session] | None = None


def get_session_factory() -> sessionmaker[Session]:
    """Return the session factory, bound to the current engine."""

    global _factory

    if _factory is None:
        _factory = sessionmaker(
            bind=get_engine(),
            autoflush=False,
            autocommit=False,
            expire_on_commit=False,
        )

    return _factory


def reset_session_factory() -> None:
    """Drop the cached factory so the next session picks up a new engine."""

    global _factory
    _factory = None


def create_session() -> Session:
    """Return a new session. The caller is responsible for closing it."""

    return get_session_factory()()


@contextmanager
def session_scope() -> Generator[Session, None, None]:
    """
    Provide a transactional session that commits on success and rolls back on error.

    Use this for any unit of work that writes.
    """

    session = create_session()

    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@contextmanager
def read_session() -> Generator[Session, None, None]:
    """Provide a read-only session that is always closed, never committed."""

    session = create_session()

    try:
        yield session
    finally:
        session.close()
