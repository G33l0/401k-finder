"""
The .cmd wrapper around build.ps1.

PowerShell refuses to run an unsigned script under the default execution
policy, with either "running scripts is disabled" or "is not digitally
signed". A .cmd file is not subject to that policy, so build.cmd is the
launch path that works on a machine nobody has configured.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
WRAPPER = ROOT / "build.cmd"
SCRIPT = ROOT / "build.ps1"


def test_the_wrapper_ships():
    assert WRAPPER.is_file()


def test_it_uses_crlf_throughout():
    """cmd.exe parses line by line and mis-reads a batch file saved with LF."""

    raw = WRAPPER.read_bytes()

    assert b"\r\n" in raw
    assert re.search(rb"(?<!\r)\n", raw) is None, "a bare LF would break cmd.exe"


def test_it_is_plain_ascii_with_no_byte_order_mark():
    """A BOM lands in the first command and cmd.exe reports it as unrecognised."""

    raw = WRAPPER.read_bytes()

    assert not raw.startswith(b"\xef\xbb\xbf")
    raw.decode("ascii")


def commands() -> str:
    """The wrapper with its REM comments stripped."""

    return "\n".join(
        line
        for line in WRAPPER.read_text(encoding="ascii").splitlines()
        if not line.strip().upper().startswith("REM")
    )


def test_it_bypasses_the_execution_policy_without_changing_the_machine():
    text = commands()

    assert "-ExecutionPolicy Bypass" in text
    assert "-NoProfile" in text
    assert "Set-ExecutionPolicy" not in text, "must not alter the machine's policy"


def test_it_runs_the_script_beside_itself():
    """%~dp0 rather than a relative path, so it works from any directory."""

    assert '"%~dp0build.ps1"' in commands()


def test_it_passes_every_argument_through():
    assert "%*" in commands()


def test_it_reports_the_build_exit_code():
    """A CI step or a caller has to be able to tell a failed build from a good one."""

    text = commands()

    assert "%ERRORLEVEL%" in text
    assert re.search(r"exit /b %\w+%", text)


@pytest.mark.parametrize("flag", ["-Clean", "-Installer", "-SkipTests", "-VenvPath"])
def test_the_documented_flags_are_real_build_script_parameters(flag):
    """The wrapper's examples must not advertise a switch build.ps1 lacks."""

    declared = SCRIPT.read_text(encoding="utf-8")
    name = flag.lstrip("-")

    assert re.search(rf"\[(switch|string)\]\${name}\b", declared), f"{flag} is not a parameter"


def test_every_flag_the_wrapper_shows_is_one_the_script_takes():
    text = WRAPPER.read_text(encoding="ascii")
    declared = SCRIPT.read_text(encoding="utf-8")

    parameters = set(re.findall(r"\[(?:switch|string)\]\$(\w+)", declared))
    shown = set(re.findall(r"build\.cmd[^\r\n]*?-(\w+)", text))

    assert shown, "the wrapper should show at least one example"
    assert shown <= parameters, f"{shown - parameters} is not a build.ps1 parameter"
