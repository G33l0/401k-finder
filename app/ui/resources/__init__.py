"""Application branding assets: the window icon, the logo and an optional theme."""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

ICON_FILE = "app.ico"
LOGO_FILE = "logo.png"
STYLESHEET_FILE = "app.qss"
USER_GUIDE_FILE = "USER_GUIDE.md"

ICON_FALLBACKS = ("app.png", "logo.png")


@lru_cache(maxsize=1)
def resource_dir() -> Path:
    """Return the folder holding the branding assets, frozen or not."""

    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        packaged = Path(bundle) / "app" / "ui" / "resources"
        if packaged.is_dir():
            return packaged

    return Path(__file__).resolve().parent


def resource_path(name: str) -> Path | None:
    """Return the path to a named asset, or None when it is not present."""

    candidate = resource_dir() / name
    return candidate if candidate.is_file() else None


def icon_path() -> Path | None:
    """Return the application icon."""

    for name in (ICON_FILE, *ICON_FALLBACKS):
        found = resource_path(name)
        if found is not None:
            return found

    return None


def user_guide_path() -> Path | None:
    """The user manual, whether running from source or from a build."""

    bundle = getattr(sys, "_MEIPASS", None)
    if bundle:
        packaged = Path(bundle) / "docs" / USER_GUIDE_FILE
        if packaged.is_file():
            return packaged

    from_source = Path(__file__).resolve().parents[3] / "docs" / USER_GUIDE_FILE
    return from_source if from_source.is_file() else None


def logo_path() -> Path | None:
    """Return the logo shown in the About dialog."""

    return resource_path(LOGO_FILE)


def stylesheet_path() -> Path | None:
    """Return the optional Qt style sheet."""

    return resource_path(STYLESHEET_FILE)


def load_stylesheet() -> str:
    """Return the style sheet's contents, or an empty string if there is none."""

    path = stylesheet_path()
    if path is None:
        return ""

    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def app_icon():  # -> QIcon | None
    """Return the application icon as a QIcon, or None."""

    path = icon_path()
    if path is None:
        return None

    from PySide6.QtGui import QIcon

    icon = QIcon(str(path))
    if icon.isNull() or not icon.availableSizes():
        return None

    return icon


def logo_pixmap(width: int = 96):  # -> QPixmap | None
    """Return the logo scaled to a width, or None when there is no logo."""

    path = logo_path()
    if path is None:
        return None

    from PySide6.QtCore import Qt
    from PySide6.QtGui import QPixmap

    pixmap = QPixmap(str(path))
    if pixmap.isNull():
        return None

    return pixmap.scaledToWidth(width, Qt.SmoothTransformation)


def describe() -> dict[str, str | None]:
    """Report which assets were found. Used by ``401k-finder status``."""

    return {
        "resource_dir": str(resource_dir()),
        "icon": str(icon_path()) if icon_path() else None,
        "logo": str(logo_path()) if logo_path() else None,
        "stylesheet": str(stylesheet_path()) if stylesheet_path() else None,
    }
