"""Desktop application entry point."""

from __future__ import annotations

import sys

from app import __version__


def main() -> int:
    """Start the desktop application."""

    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication

    from app.core.config import Settings
    from app.core.logging import configure_logging
    from app.licensing import get_gate
    from app.ui import resources, theme
    from app.ui.windows.activation_dialog import require_license
    from app.ui.windows.main_window import MainWindow
    from app.ui.windows.storage_dialog import ensure_storage_available

    configure_logging()

    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("401K Finder Pro")
    app.setApplicationDisplayName("401K Finder Pro")
    app.setApplicationVersion(__version__)
    app.setOrganizationName("401K Finder Pro")
    app.setOrganizationDomain("local.401k-finder")

    icon = resources.app_icon()
    if icon is not None:
        app.setWindowIcon(icon)

    theme.set_overlay(resources.load_stylesheet())

    settings = Settings.load()
    theme.apply(app, settings.theme)

    if not ensure_storage_available():
        return 1

    if not require_license(get_gate()):
        return 1

    window = MainWindow(settings)
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
