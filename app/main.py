"""
Desktop application entry point.

    python -m app.main        run the window
    401k-finder-gui           the installed console script

The command-line interface lives in :mod:`app.cli`.
"""

from __future__ import annotations

import sys

from app import __version__


def main() -> int:
    """Start the desktop application."""

    # Imported here rather than at module scope so that importing app.main in a
    # headless environment (a test runner, a build script) does not require Qt.
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.core.logging import configure_logging
    from app.ui.windows.main_window import MainWindow

    configure_logging()

    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("401K Finder Pro")
    app.setApplicationDisplayName("401K Finder Pro")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("401K Finder Pro")
    app.setOrganizationDomain("local.401k-finder")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
