"""
Guards on the writing the customer actually reads.

The house style is plain sentences with ordinary punctuation. Em dashes are
banned outright: they are the clearest tell that text was not written by the
person selling the product.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

BANNED = {
    "—": "em dash",
    "–": "en dash",
    "“": "curly double quote",
    "”": "curly double quote",
    "‘": "curly single quote",
    "’": "curly single quote",
}

# Two places legitimately hold these characters, and neither is prose.
ALLOWED = {
    Path("app/trace/history.py"),  # the SSN detector matches pasted dash variants
    Path("tests/test_trace.py"),   # and the test that feeds it one
    Path("tests/test_prose.py"),
}


def source_files() -> list[Path]:
    found: list[Path] = []
    for folder in ("app", "scripts", "tests"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            if path.relative_to(ROOT) not in ALLOWED:
                found.append(path)
    return found


@pytest.mark.parametrize("path", source_files(), ids=lambda p: str(p.relative_to(ROOT)))
def test_no_typographic_dashes_or_quotes(path: Path) -> None:
    text = path.read_text(encoding="utf-8")

    offenders = sorted({BANNED[ch] for ch in BANNED if ch in text})
    assert not offenders, (
        f"{path.relative_to(ROOT)} contains {', '.join(offenders)}. "
        f"Use ordinary punctuation in anything a customer may read."
    )


def test_docs_are_free_of_em_dashes() -> None:
    offenders = []
    for path in sorted(ROOT.glob("*.md")) + sorted((ROOT / "docs").glob("*.md")):
        if "—" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(ROOT)))

    assert not offenders, f"em dashes in {', '.join(offenders)}"


def test_packaging_scripts_are_free_of_em_dashes() -> None:
    """
    The installer wizard and the build script are read by customers too, and
    neither is a .py or a .md, so they slipped past the checks above.
    """

    offenders = []
    for path in sorted((ROOT / "installer").glob("*.iss")) + [
        ROOT / "build.ps1",
        ROOT / "build.cmd",
    ]:
        if path.is_file() and "—" in path.read_text(encoding="utf-8"):
            offenders.append(str(path.relative_to(ROOT)))

    assert not offenders, f"em dashes in {', '.join(offenders)}"


def _strings(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            found.append(node.value)
    return found


def test_no_ai_assistant_register_in_user_facing_text() -> None:
    """
    Phrases that read as a chatbot rather than a product. A person buying a
    licence should not be able to tell which parts were drafted by a machine.
    """

    tells = (
        "delve",
        "let's dive",
        "dive in",
        "it's worth noting",
        "it is worth noting",
        "important to note",
        "as an ai",
        "i'd be happy to",
        "i'm happy to",
        "feel free to",
        "seamless",
        "seamlessly",
        "leverage the",
        "in today's",
        "unlock the",
        "game-chang",
        "cutting-edge",
        "robust solution",
        "elevate your",
        "navigate the complexit",
        "tapestry",
        "testament to",
    )

    offenders: list[str] = []
    for folder in ("app", "scripts"):
        for path in sorted((ROOT / folder).rglob("*.py")):
            for value in _strings(path):
                lowered = value.lower()
                for tell in tells:
                    if tell in lowered:
                        offenders.append(f"{path.relative_to(ROOT)}: {tell!r}")

    assert not offenders, "\n".join(offenders)


@pytest.mark.parametrize(
    ("first", "last", "expected"),
    [
        (2009, 2023, "2009-2023"),
        (2023, 2023, "2023"),
        (None, None, "?"),
        (2019, None, "2019"),
        (None, 2019, "2019"),
    ],
)
def test_a_single_year_is_not_written_as_a_range(first, last, expected) -> None:
    """"Filed for 2023 to 2023" is the sort of thing a person never writes."""

    from app.core.constants import year_span

    assert year_span(first, last) == expected


def test_a_span_can_take_a_prose_joiner() -> None:
    from app.core.constants import year_span

    assert year_span(2015, 2019, joiner=" to ") == "2015 to 2019"
    assert year_span(2015, 2015, joiner=" to ") == "2015"
