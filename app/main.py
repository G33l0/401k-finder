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
    from app.licensing import get_gate
    from app.ui import resources
    from app.ui.windows.activation_dialog import require_license
    from app.ui.windows.main_window import MainWindow

    configure_logging()

    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("401K Finder Pro")
    app.setApplicationDisplayName("401K Finder Pro")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("401K Finder Pro")
    app.setOrganizationDomain("local.401k-finder")

    # Branding is optional: the application runs with Qt's defaults when
    # app/ui/resources is empty. See docs/DEPLOY.md.
    icon = resources.app_icon()
    if icon is not None:
        app.setWindowIcon(icon)

    stylesheet = resources.load_stylesheet()
    if stylesheet:
        app.setStyleSheet(stylesheet)

    # Activation runs before the main window is built. A build with no store
    # configured passes straight through, so development is unaffected.
    if not require_license(get_gate()):
        return 1

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
