"""
Application branding assets: the window icon, the logo and an optional theme.

None of these files are required — the application runs with Qt's defaults if
the folder is empty — so every accessor returns None rather than raising when an
asset is absent. See ``docs/DEPLOY.md`` for the file specifications.

Resolving the folder is the fiddly part. Running from source it sits next to
this module, but in a PyInstaller build the Python modules live inside a
compressed archive while the data files are unpacked beside the executable, so
``__file__`` points somewhere that does not exist on disk. PyInstaller records
the real location in ``sys._MEIPASS``, which is checked first.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path

#: Filenames this module looks for, relative to the resources folder.
ICON_FILE = "app.ico"
LOGO_FILE = "logo.png"
STYLESHEET_FILE = "app.qss"

#: Fallbacks for the window icon on platforms that do not use .ico files.
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
    """
    Return the application icon.

    Windows wants an ``.ico``; other platforms cannot read one, so a PNG is
    accepted as a fallback and Qt is left to scale it.
    """

    for name in (ICON_FILE, *ICON_FALLBACKS):
        found = resource_path(name)
        if found is not None:
            return found

    return None


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
    """
    Return the application icon as a QIcon, or None.

    A malformed icon file yields a QIcon that is not null but carries no images,
    which would show as a blank square rather than an error. Both conditions are
    treated as "no icon" so the application falls back to Qt's default instead.

    Qt is imported lazily so that this module stays importable in a headless
    process — the CLI and the test suite both import it without a display.
    """

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
