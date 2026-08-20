"""
The manual, and the Help menu entry that opens it.

The guide is the product for anybody who is not a researcher, so a build that
ships without it, or a link in it that goes nowhere, is a real defect.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
GUIDE = ROOT / "docs" / "USER_GUIDE.md"


def text() -> str:
    return GUIDE.read_text(encoding="utf-8")


def flowed() -> str:
    """The guide as one lowercase line, so a match is not thrown by wrapping."""

    return " ".join(text().lower().split())


def test_the_guide_ships():
    assert GUIDE.is_file()
    assert len(text()) > 8000, "a stub is worse than none"


def test_the_application_can_find_it_from_source():
    from app.ui import resources

    found = resources.user_guide_path()

    assert found is not None
    assert found.samefile(GUIDE)


def test_the_build_carries_it():
    """Frozen, it is read by path, so PyInstaller cannot see it by imports."""

    spec = (ROOT / "installer" / "401k-finder.spec").read_text(encoding="utf-8")

    assert "USER_GUIDE.md" in spec, "Help -> User guide would be empty in a build"


def test_every_contents_entry_points_at_a_real_heading():
    body = text()

    anchors = re.findall(r"\]\(#([a-z0-9-]+)\)", body)
    headings = {
        re.sub(r"[^a-z0-9 -]", "", line.lstrip("#").strip().lower()).replace(" ", "-")
        for line in body.splitlines()
        if line.startswith("#")
    }

    assert anchors, "the contents list should link to the sections"

    missing = [anchor for anchor in anchors if anchor not in headings]
    assert not missing, f"contents links with no matching heading: {missing}"


def test_it_says_what_the_data_cannot_do():
    """A guide that oversells this would be the thing that gets somebody hurt."""

    body = flowed()

    assert "cannot tell you whether you personally have a balance" in body
    assert "no participant name" in body
    assert "form 5500-ez" in body
    assert "governmental 457(b)" in body


def test_it_warns_about_the_social_security_number():
    body = flowed()

    assert "never send your social security number in an email" in body
    assert "never type a social security number" in body


def test_it_flags_the_contact_details_as_the_applications_own():
    """A number we added must never read as something the employer filed."""

    body = flowed()

    assert "added by this application" in body
    assert "check the number on the firm's own website" in body


def test_it_covers_the_features_it_promises():
    body = text()

    for feature in (
        "Find my accounts",
        "Find plans",
        "Providers",
        "Service providers by year",
        "Index every year",
        "Where the data is kept",
    ):
        assert feature in body, f"the guide never mentions {feature}"


def test_the_takeover_table_matches_the_directory():
    """If the guide and the data disagree, one of them is lying to somebody."""

    from app.providers.directory import CONTACTS

    body = text()
    successors = [contact for contact in CONTACTS if contact.successor]

    assert successors

    for contact in successors:
        assert contact.canonical_name.split(" /")[0].split()[0] in body or (
            contact.successor.split()[0] in body
        ), f"{contact.canonical_name} has a successor note the guide never mentions"


# ----------------------------------------------------------------------
# The dialog
# ----------------------------------------------------------------------


@pytest.fixture()
def qt_app():
    import os

    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QApplication = pytest.importorskip("PySide6.QtWidgets").QApplication

    yield QApplication.instance() or QApplication([])


def test_the_dialog_renders_the_guide(qt_app):
    from app.ui.windows.guide_dialog import GuideDialog

    dialog = GuideDialog()
    rendered = dialog.view.toPlainText()

    assert "finding who holds your retirement money" in rendered
    assert "Find my accounts" in rendered
    assert len(rendered) > 8000


def test_the_dialog_survives_a_missing_guide(qt_app, monkeypatch):
    """A build that dropped the file should say so, not crash on opening Help."""

    from app.ui import resources
    from app.ui.windows import guide_dialog

    monkeypatch.setattr(guide_dialog.resources, "user_guide_path", lambda: None)

    dialog = guide_dialog.GuideDialog()

    assert "not installed" in dialog.view.toPlainText()
    assert resources.user_guide_path is not None


def test_the_dialog_follows_the_active_theme(qt_app):
    from app.ui import theme
    from app.ui.windows.guide_dialog import GuideDialog

    dialog = GuideDialog()

    for key in ("light", "dark", "contrast"):
        theme.resolve(key)
        theme._current = theme.THEMES[key]
        dialog.reload()
        assert dialog.view.document().defaultStyleSheet()

    theme._current = theme.THEMES[theme.DEFAULT_THEME]


def test_the_help_menu_offers_the_guide(qt_app, imported):
    from app.core.config import Settings
    from app.ui.windows.main_window import MainWindow

    window = MainWindow(Settings())
    try:
        labels = [
            action.text().replace("&", "")
            for menu in window.menuBar().findChildren(type(window.menuBar().addMenu("x")))
            for action in menu.actions()
        ]
        assert "User guide" in labels
    finally:
        window.close()
