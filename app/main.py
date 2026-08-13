from __future__ import annotations

import sys

from PySide6.QtWidgets import QApplication

from app.ui.windows.main_window import MainWindow


def main() -> int:
    """Application entry point."""
    app = QApplication(sys.argv)

    app.setApplicationName("401K Finder Pro")
    app.setApplicationDisplayName("401K Finder Pro")
    app.setOrganizationName("401K Finder Pro")
    app.setOrganizationDomain("local.401k-finder")

    window = MainWindow()
    window.show()

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())