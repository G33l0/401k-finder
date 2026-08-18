"""
Guards against code that cannot run on Windows.

This is a Windows product developed on Linux, so a POSIX-only call passes
every check here and then fails on the machine the customer builds on. It
already happened once: a test called os.geteuid() to skip itself when run as
root, and stopped the Windows build dead with AttributeError.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

#: Attributes of os that simply do not exist on Windows.
POSIX_ONLY_OS = {
    "geteuid",
    "getuid",
    "getegid",
    "getgid",
    "setuid",
    "setgid",
    "seteuid",
    "getgroups",
    "getpgid",
    "getpgrp",
    "setsid",
    "fork",
    "forkpty",
    "uname",
    "mkfifo",
    "chown",
    "lchown",
    "statvfs",
    "getpriority",
    "nice",
    "killpg",
    "wait3",
    "wait4",
    "sysconf",
    "confstr",
    "getloadavg",
}

#: Modules that only import on POSIX.
POSIX_ONLY_MODULES = {"pwd", "grp", "fcntl", "termios", "tty", "posix", "crypt", "resource"}

#: Modules that only import on Windows.
WINDOWS_ONLY_MODULES = {"winreg", "msvcrt", "winsound", "_winapi"}


def source_files() -> list[Path]:
    found: list[Path] = []
    for folder in ("app", "scripts", "tests"):
        found.extend(sorted((ROOT / folder).rglob("*.py")))
    return found


def _ids(path: Path) -> str:
    return str(path.relative_to(ROOT))


def _guards_the_platform(text: str) -> bool:
    """The file decides what to do per platform rather than assuming one."""

    return "sys.platform" in text or "platform.system" in text or "os.name" in text


@pytest.mark.parametrize("path", source_files(), ids=_ids)
def test_no_posix_only_module_is_imported_unguarded(path: Path) -> None:
    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)

    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module.split(".")[0])

    posix = found & POSIX_ONLY_MODULES
    windows = found & WINDOWS_ONLY_MODULES

    if posix or windows:
        assert _guards_the_platform(text), (
            f"{_ids(path)} imports {sorted(posix | windows)} without checking the platform"
        )


@pytest.mark.parametrize("path", source_files(), ids=_ids)
def test_no_posix_only_os_call_is_made_unguarded(path: Path) -> None:
    """
    os.geteuid() and friends raise AttributeError on Windows. A file using one
    has to decide per platform, and a test using one needs a skipif so it never
    runs there at all.
    """

    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)

    offenders: list[str] = []

    for node in ast.walk(tree):
        if not (isinstance(node, ast.Attribute) and node.attr in POSIX_ONLY_OS):
            continue
        if not (isinstance(node.value, ast.Name) and node.value.id == "os"):
            continue

        owner = _enclosing_function(tree, node)

        if owner is not None and _has_platform_skip(owner):
            continue
        if _guards_the_platform(text):
            continue

        offenders.append(f"line {node.lineno}: os.{node.attr}()")

    assert not offenders, (
        f"{_ids(path)} calls {', '.join(offenders)}, which does not exist on Windows. "
        f"Guard it with sys.platform, or mark the test skipif(sys.platform == 'win32')."
    )


def _enclosing_function(tree: ast.AST, target: ast.AST):  # noqa: ANN202
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for inner in ast.walk(node):
                if inner is target:
                    return node
    return None


def _has_platform_skip(function) -> bool:  # noqa: ANN001
    """A skipif decorator that mentions the platform."""

    for decorator in function.decorator_list:
        rendered = ast.unparse(decorator)
        if "skipif" in rendered and ("platform" in rendered or "os.name" in rendered):
            return True
    return False


@pytest.mark.parametrize("path", source_files(), ids=_ids)
def test_no_absolute_posix_path_is_hardcoded(path: Path) -> None:
    """
    "/tmp/..." and "/etc/..." are not paths on Windows. Real ones belong behind
    tempfile or a platform check; the fixtures use tmp_path.
    """

    text = path.read_text(encoding="utf-8")
    tree = ast.parse(text)

    roots = ("/tmp/", "/var/", "/usr/", "/home/", "/opt/", "/etc/")
    offenders = [
        f"line {node.lineno}: {node.value!r}"
        for node in ast.walk(tree)
        if isinstance(node, ast.Constant)
        and isinstance(node.value, str)
        and node.value.startswith(roots)
    ]

    if offenders:
        assert _guards_the_platform(text), (
            f"{_ids(path)} hardcodes {'; '.join(offenders)}, which is not a path on Windows"
        )


def test_the_guard_would_have_caught_the_original_fault(tmp_path: Path) -> None:
    """The exact shape that stopped a Windows build."""

    offending = tmp_path / "bad_test.py"
    offending.write_text(
        "import os\n"
        "\n"
        "def test_something():\n"
        "    if os.geteuid() == 0:\n"
        "        return\n",
        encoding="utf-8",
    )

    tree = ast.parse(offending.read_text(encoding="utf-8"))
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Attribute)
        and node.attr in POSIX_ONLY_OS
        and isinstance(node.value, ast.Name)
        and node.value.id == "os"
    ]

    assert calls, "the scanner must see the call"
    assert not _guards_the_platform(offending.read_text(encoding="utf-8"))
    assert not _has_platform_skip(_enclosing_function(tree, calls[0]))


# ----------------------------------------------------------------------
# Text encoding
# ----------------------------------------------------------------------


def _text_calls(tree: ast.AST):  # noqa: ANN202
    """Every open/read_text/write_text that handles text rather than bytes."""

    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue

        is_method = isinstance(node.func, ast.Attribute)
        name = node.func.attr if is_method else getattr(node.func, "id", None)
        if name not in {"open", "write_text", "read_text"}:
            continue

        if name in {"write_text", "read_text"}:
            yield node, name
            continue

        # Path.open() takes the mode first; the builtin open() takes it second.
        index = 0 if is_method else 1
        mode = None
        if len(node.args) > index and isinstance(node.args[index], ast.Constant):
            mode = node.args[index].value
        for keyword in node.keywords:
            if keyword.arg == "mode" and isinstance(keyword.value, ast.Constant):
                mode = keyword.value.value

        if mode is None and len(node.args) > index:
            continue  # a variable mode; cannot tell statically
        if isinstance(mode, str) and "b" in mode:
            continue  # binary needs no encoding

        yield node, name


@pytest.mark.parametrize("path", source_files(), ids=_ids)
def test_text_files_are_read_and_written_as_utf8(path: Path) -> None:
    """
    Without encoding=, Python uses the locale default. That is UTF-8 on the
    machine this is developed on and cp1252 on the machine it is sold for, so
    a plan name with an accent in it raises UnicodeEncodeError only for the
    customer.
    """

    tree = ast.parse(path.read_text(encoding="utf-8"))

    offenders = [
        f"line {node.lineno}: {name}()"
        for node, name in _text_calls(tree)
        if not any(keyword.arg == "encoding" for keyword in node.keywords)
    ]

    assert not offenders, (
        f"{_ids(path)} has {', '.join(offenders)} with no encoding=. "
        f"Pass encoding='utf-8' so Windows does not fall back to cp1252."
    )


def test_a_report_survives_a_plan_name_windows_cannot_encode(tmp_path: Path) -> None:
    """
    cp1252 cannot represent these. Writing the report without encoding= would
    raise for the customer and never for us.
    """

    # Built from escapes so the house style guard does not read the sample as
    # prose. cp1252 cannot represent any of these.
    awkward = "CAF\u00c9 M\u00dcNCHEN 401(K) PLAN \u2014 \u65e5\u672c\u8a9e \u20ac"
    target = tmp_path / "report.txt"

    target.write_text(awkward, encoding="utf-8")

    assert target.read_text(encoding="utf-8") == awkward
