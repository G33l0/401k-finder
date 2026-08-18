from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture(scope="session")
def repo_root() -> Path:
    return REPO_ROOT


@pytest.fixture(scope="session", autouse=True)
def isolated_data_dir(tmp_path_factory) -> Path:
    """Point the application at a throwaway data directory for the whole session."""

    path = tmp_path_factory.mktemp("finder-data")
    os.environ["FINDER_401K_DATA_DIR"] = str(path)
    return path


@pytest.fixture(scope="session")
def dol_files(tmp_path_factory, isolated_data_dir) -> Path:
    """Generate synthetic DOL files with real layout column sets."""

    from scripts.make_test_data import generate

    directory = tmp_path_factory.mktemp("dol")
    generate(year=2023, plan_count=24, output=directory, seed=11)
    return directory


@pytest.fixture()
def engine(tmp_path, isolated_data_dir):
    """A fresh database per test."""

    from app.database.engine import create_database_engine, dispose_engine, set_engine
    from app.database.schema import initialize_database
    from app.database.session import reset_session_factory

    database_path = tmp_path / "test.sqlite3"
    new_engine = create_database_engine(database_path)

    set_engine(new_engine)
    reset_session_factory()
    initialize_database(new_engine)

    yield new_engine

    dispose_engine()
    reset_session_factory()


@pytest.fixture()
def session(engine):
    from app.database.session import create_session

    handle = create_session()
    try:
        yield handle
    finally:
        handle.close()


@pytest.fixture()
def imported(session, dol_files):
    """A database with the synthetic 2023 data imported."""

    from app.database.schema import rebuild_fts
    from app.dol.importer import import_directory

    stats = import_directory(session, dol_files, form_year=2023)
    rebuild_fts(session.get_bind())

    return stats
