"""The user manual, shown inside the application."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

from app.ui import resources, theme


class GuideDialog(QDialog):
    """A scrollable, searchable copy of docs/USER_GUIDE.md."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.setWindowTitle("User guide")
        self.resize(940, 760)

        layout = QVBoxLayout(self)

        self.view = QTextBrowser()
        self.view.setOpenExternalLinks(False)
        self.view.setOpenLinks(False)
        layout.addWidget(self.view, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

        self.reload()

    def reload(self) -> None:
        """Render the guide in the active theme."""

        palette = theme.current()
        self.view.document().setDefaultStyleSheet(theme.document_css(palette))

        path = resources.user_guide_path()
        if path is None:
            self.view.setPlainText(
                "The user guide was not installed with this copy of the "
                "application.\n\nIt is also published with the source, as "
                "docs/USER_GUIDE.md."
            )
            return

        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            self.view.setPlainText(f"The user guide could not be read: {exc}")
            return

        self.view.setMarkdown(text)
        self.view.verticalScrollBar().setValue(0)


def show_guide(parent: QWidget | None = None) -> GuideDialog:
    """Open the guide, reusing the window if it is already up."""

    existing = getattr(parent, "_guide_dialog", None)

    if existing is None:
        existing = GuideDialog(parent)
        if parent is not None:
            parent._guide_dialog = existing  # noqa: SLF001 - the window owns it
    else:
        existing.reload()

    existing.show()
    existing.raise_()
    existing.activateWindow()

    return existing
