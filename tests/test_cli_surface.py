"""
The command line as a user meets it.

Every one of these was a Python traceback printed at somebody who typed a
plausible command. A shipped tool answers in sentences.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def run(*args: str, stdin: str | None = "", data_dir: Path | None = None):
    env = dict(os.environ, QT_QPA_PLATFORM="offscreen")
    if data_dir is not None:
        env["FINDER_401K_DATA_DIR"] = str(data_dir)

    return subprocess.run(
        [sys.executable, "-m", "app.cli", *args],
        capture_output=True,
        text=True,
        input=stdin,
        env=env,
        cwd=ROOT,
        timeout=120,
    )


def assert_no_traceback(result) -> None:  # noqa: ANN001
    blob = result.stdout + result.stderr
    assert "Traceback (most recent call last)" not in blob, blob[-1200:]


def test_version_is_reported(tmp_path):
    from app import __version__

    result = run("--version", data_dir=tmp_path)

    assert result.returncode == 0
    assert __version__ in result.stdout


def test_importing_a_folder_that_is_not_there_says_so(tmp_path):
    result = run("import", str(tmp_path / "nope"), data_dir=tmp_path)

    assert_no_traceback(result)
    assert result.returncode == 1
    assert "no folder" in result.stderr.lower()


def test_importing_a_file_rather_than_a_folder_says_so(tmp_path):
    target = tmp_path / "a-file.csv"
    target.write_text("ACK_ID\n", encoding="utf-8")

    result = run("import", str(target), data_dir=tmp_path)

    assert_no_traceback(result)
    assert result.returncode == 1


def test_reset_with_nothing_on_stdin_explains_itself(tmp_path):
    """A scheduled task or a piped run has no terminal to answer the prompt."""

    result = run("init", data_dir=tmp_path)
    assert result.returncode == 0

    result = run("reset", stdin="", data_dir=tmp_path)

    assert_no_traceback(result)
    assert result.returncode == 1
    assert "--yes" in result.stderr


def test_indexing_an_unpublished_year_is_refused(tmp_path):
    """It used to print a progress bar and report success for form year 1800."""

    result = run("index", "--year", "1800", data_dir=tmp_path)

    assert_no_traceback(result)
    assert result.returncode == 1
    assert "1800" in result.stderr
    assert "available" in result.stderr


def test_syncing_an_unpublished_year_is_refused(tmp_path):
    result = run("sync", "--year", "1990", data_dir=tmp_path)

    assert_no_traceback(result)
    assert result.returncode == 1


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("nosuchcommand",),
        ("status",),
        ("datasets",),
        ("search",),
        ("search", "acme"),
        ("search", '*"()^:-'),
        ("search", "'; DROP TABLE plans; --"),
        ("plan", "abc"),
        ("plan", "-1"),
        ("providers", "*"),
        ("changes",),
        ("trace", "--employer", "acme"),
        ("trace", "--employer", ""),
        ("trace", "--history", "/nonexistent.csv"),
        ("storage",),
        ("storage", "list"),
        ("storage", "set", "/nonexistent/deeper"),
        ("license", "status"),
        ("license", "activate", "junk"),
    ],
)
def test_no_command_ends_in_a_traceback(args, tmp_path):
    assert_no_traceback(run(*args, data_dir=tmp_path))


FRESH_INSTALL_READS = [
    ("search", "acme"),
    ("plan", "12-3456789"),
    ("providers", "fidelity"),
    ("changes",),
    ("trace", "--employer", "acme"),
]


@pytest.mark.parametrize("args", FRESH_INSTALL_READS, ids=lambda a: a[0])
def test_a_read_on_a_fresh_install_explains_itself(args, tmp_path):
    """
    "search" was the first thing a new customer typed, and it answered with
    forty lines of SQLAlchemy ending in "no such table: plans".
    """

    result = run(*args, data_dir=tmp_path)

    assert_no_traceback(result)
    assert result.returncode == 1
    assert "No data yet" in result.stderr
    assert "401k-finder init" in result.stderr


def test_every_read_command_says_the_same_thing(tmp_path):
    """One product, one voice. These used to have three different wordings."""

    messages = set()
    for args in FRESH_INSTALL_READS:
        directory = tmp_path / args[0]
        directory.mkdir()
        messages.add(run(*args, data_dir=directory).stderr.strip())

    assert len(messages) == 1, messages


def test_status_reports_a_fresh_install_rather_than_failing(tmp_path):
    """Asking what is installed is a fair question before anything is."""

    result = run("status", data_dir=tmp_path)

    assert_no_traceback(result)
    assert result.returncode == 0
    assert "Not created yet" in result.stdout
