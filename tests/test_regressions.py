"""Regression tests for bugs found by auditing rather than by a failing test."""

from __future__ import annotations

from pathlib import Path
from unittest import mock

import pytest

from app.search.engine import TEXT_MATCH_CAP, SearchEngine
from app.search.query import PlanQuery


def test_windows_data_dir_is_not_nested_twice():
    r"""
    platformdirs nests under the author name on Windows. Passing an author equal to the
    application name produced "%LOCALAPPDATA%\401K Finder Pro\401K Finder Pro", while
    every document describes a single folder.
    """

    from platformdirs.windows import Windows

    with mock.patch(
        "platformdirs.windows.get_win_folder",
        lambda _: r"C:\Users\Someone\AppData\Local",
    ):
        resolved = Windows(appname="401K Finder Pro", appauthor=False).user_data_dir

    assert resolved.count("401K Finder Pro") == 1


def test_config_does_not_pass_an_app_author():
    """The nesting above is only avoided while appauthor stays False."""

    source = Path("app/core/config.py").read_text(encoding="utf-8")
    assert "appauthor=False" in source
    assert "APP_AUTHOR" not in source


def test_detect_encoding_closes_its_handle(tmp_path):
    """
    Windows refuses to delete an open file, and the sync service deletes these
    CSVs once the import finishes.
    """

    from app.dol.csv_reader import detect_encoding

    sample = tmp_path / "sample.csv"
    sample.write_text("ACK_ID,PLAN_NAME\n1,Test\n", encoding="utf-8")

    detect_encoding(sample)

    sample.unlink()
    assert not sample.exists()


def test_capped_text_search_reports_a_lower_bound(session, imported, monkeypatch):
    """
    Text search reads at most TEXT_MATCH_CAP matches before filtering. Reporting
    that ceiling as an exact total would be plainly wrong for a broad term.
    """

    engine = SearchEngine(session)

    monkeypatch.setattr("app.search.engine.TEXT_MATCH_CAP", 1)

    total, capped = engine.count_plans_detailed(PlanQuery(text="acme"))

    assert capped is True
    assert total >= 1


def test_uncapped_search_reports_an_exact_count(session, imported):
    engine = SearchEngine(session)
    total, capped = engine.count_plans_detailed(PlanQuery(text="acme"))

    assert capped is False
    assert total == len(engine.search_plans(PlanQuery(text="acme", limit=500)))


def test_text_match_cap_is_sane():
    assert TEXT_MATCH_CAP >= 1000


def test_downloader_resumes_on_the_first_attempt():
    """
    Resume was gated on `attempt > 1`, so a part file left by an interrupted
    run was discarded and the multi-gigabyte download restarted from zero.
    """

    source = Path("app/dol/downloader.py").read_text(encoding="utf-8")
    assert "resume=resume and attempt > 1" not in source
    assert "resume=resume," in source


def test_importer_does_not_preload_every_engagement():
    """
    The engagement cache held one entry per plan-provider-role-year-schedule.
    Across a full form year that runs into the millions and dominates memory;
    the table's unique constraint does the same job.
    """

    source = Path("app/dol/importer.py").read_text(encoding="utf-8")

    assert "self._party_keys" not in source
    assert 'prefix_with("OR IGNORE")' in source


def test_schedule_dedupe_is_scoped_to_the_batch():
    """A file-wide set grew to one entry per row on multi-million-row files."""

    source = Path("app/dol/importer.py").read_text(encoding="utf-8")
    assert "seen_records.clear()" in source


def test_reimport_still_deduplicates_engagements(session, dol_files, imported):
    """
    OR IGNORE replaced the in-memory guard, so re-import must still be a no-op.
    """

    from sqlalchemy import func, select

    from app.database.models import PlanParty
    from app.dol.importer import import_directory

    before = session.execute(select(func.count(PlanParty.id))).scalar()
    import_directory(session, dol_files, form_year=2023)
    after = session.execute(select(func.count(PlanParty.id))).scalar()

    assert before == after


@pytest.fixture(scope="module")
def build_script() -> str:
    return Path("build.ps1").read_text(encoding="utf-8")


def test_build_installs_the_test_dependencies(build_script):
    """requirements.txt is runtime-only; pytest lives in requirements-dev.txt."""

    assert "requirements-dev.txt" in build_script


def test_build_verifies_its_tools_before_using_them(build_script):
    for module in ("PySide6", "sqlalchemy", "PyInstaller", "pytest"):
        assert module in build_script


def test_build_joins_output_before_matching(build_script):
    """
    `-notmatch` against an array filters it rather than returning a boolean,
    so the smoke test threw on every otherwise-good build.
    """

    assert "-notmatch" not in build_script or '-join "`n") -notmatch' in build_script


def test_build_measures_only_files(build_script):
    """Directories have no Length; asking for it aborts under Stop."""

    assert "-Recurse -File | Measure-Object" in build_script


def test_build_checks_the_packaged_output_not_the_source(build_script):
    """
    A layout check that imports from the source tree passes even when
    PyInstaller dropped every data file.
    """

    assert "_internal\\app\\dol\\layouts\\data" in build_script


def test_installer_handles_older_inno_setup():
    """x64compatible does not exist before Inno Setup 6.3 and fails the compile."""

    script = Path("installer/401k-finder.iss").read_text(encoding="utf-8")
    assert "#if Ver >= EncodeVer(6,3,0,0)" in script
    assert "ArchitecturesAllowed=x64\n" in script


def test_installer_ships_both_executables():
    script = Path("installer/401k-finder.iss").read_text(encoding="utf-8")
    assert "{#AppExeName}" in script
    assert "{#CliExeName}" in script


def test_reimport_does_not_duplicate_evidence(session, dol_files, imported):
    """
    Only engagements had a unique constraint, so a second import appended a
    fresh copy of every citation, inflating the trail while adding nothing.
    """

    from sqlalchemy import func, select

    from app.database.models import Evidence
    from app.dol.importer import import_directory

    before = session.execute(select(func.count(Evidence.id))).scalar()
    import_directory(session, dol_files, form_year=2023)
    after = session.execute(select(func.count(Evidence.id))).scalar()

    assert before == after


def test_evidence_uniqueness_is_enforced_by_the_schema(engine):
    """The guarantee must live in the database, not only in the import path."""

    from sqlalchemy import inspect

    indexes = inspect(engine).get_indexes("evidence")
    names = {index["name"] for index in indexes}

    assert "uq_evidence_source_field" in names


def test_migration_removes_pre_existing_duplicate_evidence(tmp_path):
    """
    Databases written before schema 4 may already hold duplicates, so the
    upgrade collapses them before creating the index that forbids them.
    """

    import sqlite3

    from app.database.engine import create_database_engine
    from app.database.schema import initialize_database

    path = tmp_path / "legacy.sqlite3"

    raw = sqlite3.connect(path)
    raw.executescript(
        """
        CREATE TABLE evidence (
            id INTEGER NOT NULL PRIMARY KEY,
            plan_id INTEGER NOT NULL,
            form_year INTEGER NOT NULL,
            ack_id VARCHAR(40),
            source_type VARCHAR(60) NOT NULL,
            dataset VARCHAR(60),
            source_row INTEGER,
            field_name VARCHAR(120),
            created_at DATETIME NOT NULL
        );
        CREATE TABLE schema_version (version INTEGER NOT NULL, applied_at TEXT);
        INSERT INTO schema_version VALUES (3, '2026-01-01');
        """
    )
    for _ in range(3):
        raw.execute(
            "INSERT INTO evidence (plan_id, form_year, ack_id, source_type, dataset,"
            " source_row, field_name, created_at)"
            " VALUES (1, 2023, 'ACK1', 'DOL_DATASET', 'F_SCH_H', 2, 'FDCRY_TRUST_NAME', '2026')"
        )
    raw.commit()
    raw.close()

    initialize_database(create_database_engine(path))

    check = sqlite3.connect(path)
    remaining = check.execute("SELECT COUNT(*) FROM evidence").fetchone()[0]
    version = check.execute("SELECT MAX(version) FROM schema_version").fetchone()[0]
    check.close()

    assert remaining == 1, "duplicates were not collapsed before the index was added"
    assert version >= 4


def test_status_does_not_crash_before_the_database_exists(tmp_path, capsys, monkeypatch):
    """
    'status' is the first command a fresh installation runs, and the deployment
    guide says to run it to confirm the branding was picked up. It used to
    query the plans table straight away and fail with a SQLAlchemy traceback on
    a machine where the application had never been opened.
    """

    import argparse

    from app.cli import cmd_status
    from app.core import config

    monkeypatch.setattr(config, "get_app_data_dir", lambda: tmp_path)
    monkeypatch.setattr("app.cli.get_database_path", lambda: tmp_path / "absent.sqlite3")
    monkeypatch.setattr("app.cli.database_exists", lambda: False)

    assert cmd_status(argparse.Namespace(branding=True, year=None)) == 0

    printed = capsys.readouterr().out
    assert "Not created yet" in printed
    assert "Resource folder" in printed


def test_database_exists_is_false_for_an_absent_or_empty_file(tmp_path):
    """Opening a SQLite file creates it, so the check has to be on the file."""

    from app.database.init_db import database_exists

    assert not database_exists(tmp_path / "nothing-here.sqlite3")

    empty = tmp_path / "empty.sqlite3"
    empty.touch()
    assert not database_exists(empty), "a zero-byte file has no tables in it"

    empty.write_bytes(b"SQLite format 3\x00")
    assert database_exists(empty)


def test_an_existing_v4_database_gains_the_transfers_table(tmp_path):
    """
    Customers upgrading arrive at schema 4 with no plan_transfers table.
    Step 1 creates every table in the current metadata, so a database built
    today already has it, so this simulates the real starting point instead.
    """

    import sqlite3

    from app.database.engine import create_database_engine
    from app.database.init_db import initialize_database

    path = tmp_path / "v4.sqlite3"
    initialize_database(create_database_engine(path))

    raw = sqlite3.connect(path)
    raw.execute("DROP TABLE plan_transfers")
    raw.execute("DELETE FROM schema_version WHERE version > 4")
    raw.commit()
    assert raw.execute("SELECT MAX(version) FROM schema_version").fetchone()[0] == 4
    raw.close()

    assert initialize_database(create_database_engine(path)) == 5

    check = sqlite3.connect(path)
    present = check.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='plan_transfers'"
    ).fetchone()
    check.close()

    assert present is not None


@pytest.mark.parametrize(
    "value",
    [
        "99999999999999999999",
        "-99999999999999999999",
        "9223372036854775808",
        "-9223372036854775809",
    ],
)
def test_a_count_too_large_for_sqlite_is_not_reported(value):
    """
    SQLite integers are signed 64-bit. A filing carrying more than that used to
    reach the insert and raise OverflowError, which aborted the whole file:
    one mistyped participant count discarded a year of filings.
    """

    from app.dol.normalizer import parse_int

    assert parse_int(value) is None


def test_the_64_bit_boundaries_themselves_still_parse():
    from app.dol.normalizer import parse_int

    assert parse_int("9223372036854775807") == 2**63 - 1
    assert parse_int("-9223372036854775808") == -(2**63)


@pytest.mark.parametrize("value", ["nan", "NaN", "inf", "-inf", "Infinity"])
def test_non_finite_amounts_are_not_reported(value):
    """Decimal accepts these. Neither is an amount, and both poison every SUM."""

    from app.dol.normalizer import parse_decimal, parse_money

    assert parse_decimal(value) is None
    assert parse_money(value) is None


def test_an_amount_too_large_for_a_float_is_not_reported():
    """
    Decimal carries an arbitrary exponent, so 1e400 is finite to it and only
    overflows on the way to the float column the database actually stores.
    """

    from app.dol.normalizer import parse_decimal, parse_money

    assert parse_decimal("1e400").is_finite()
    assert parse_money("1e400") is None


def test_one_unusable_number_does_not_discard_the_whole_file(session, tmp_path):
    """The regression this guards: 100 filings lost because row 42 had a typo."""

    from app.dol.importer import import_directory

    header = (
        "ACK_ID,SPONS_DFE_EIN,SPONS_DFE_PN,PLAN_NAME,SPONSOR_DFE_NAME,"
        "FORM_PLAN_YEAR_BEGIN_DATE,TOT_PARTCP_BOY_CNT\n"
    )
    rows = [
        f"2044{index:08d}NAL{index:07d}001,04{index:07d},001,"
        f"OVERFLOW PLAN {index},OVERFLOW SPONSOR {index},2023-01-01,"
        f"{'99999999999999999999' if index == 7 else 100 + index}\n"
        for index in range(20)
    ]

    directory = tmp_path / "files"
    directory.mkdir()
    (directory / "F_5500_2023_latest.csv").write_text(header + "".join(rows))

    stats = import_directory(session, directory, form_year=2023)

    assert stats.rows_imported == 20, stats.errors
    assert not stats.errors
