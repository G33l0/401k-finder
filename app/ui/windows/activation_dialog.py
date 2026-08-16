"""
The activation window shown when a build requires a licence.

This is the first thing a paying customer sees, and often the first thing they
see when something has gone wrong, so it aims to be a place where every route
forward is visible: buy, activate, get help, or copy the details support will
ask for.

Activation runs on a worker thread. It is a network call, and freezing the
window while it completes would make a slow connection look like a crash.
"""

from __future__ import annotations

from PySide6.QtCore import Qt, QThread, QUrl, Signal
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.licensing import LicenseGate, LicenseState, machine_fingerprint
from app.licensing.models import ActivationResult
from app.ui import resources, theme


class _ActivationWorker(QThread):
    """Runs one activation attempt off the UI thread."""

    completed = Signal(object)

    def __init__(self, gate: LicenseGate, key: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._gate = gate
        self._key = key

    def run(self) -> None:
        try:
            result = self._gate.activate(self._key)
        except Exception as exc:  # noqa: BLE001 - surfaced in the dialog
            result = ActivationResult(
                ok=False,
                state=LicenseState.UNLICENSED,
                message=f"Activation failed: {exc}",
            )

        self.completed.emit(result)


class ActivationDialog(QDialog):
    """Collects a licence key and activates it."""

    def __init__(self, gate: LicenseGate, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.gate = gate
        self._worker: _ActivationWorker | None = None
        self.activated = False

        self.setWindowTitle("Activate 401K Finder Pro")
        self.setMinimumWidth(520)

        icon = resources.app_icon()
        if icon is not None:
            self.setWindowIcon(icon)

        self._build()

    # ------------------------------------------------------------------

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        heading = QLabel(f"<h2 style='margin:0'>401K Finder Pro {__version__}</h2>")
        heading.setTextFormat(Qt.RichText)
        layout.addWidget(heading)

        intro = QLabel(
            "Enter the licence key from your purchase confirmation email.<br>"
            "The key is tied to this computer once activated."
        )
        intro.setTextFormat(Qt.RichText)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.key_input = QLineEdit()
        self.key_input.setPlaceholderText("XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX")
        self.key_input.textChanged.connect(self._on_key_changed)
        self.key_input.returnPressed.connect(self._activate)
        layout.addWidget(self.key_input)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setVisible(False)
        layout.addWidget(self.message)

        rule = QFrame()
        rule.setFrameShape(QFrame.HLine)
        rule.setFrameShadow(QFrame.Sunken)
        layout.addWidget(rule)

        # Buying and support are given equal weight to activating: someone who
        # arrived here without a key needs a route forward, not a dead end.
        links = QHBoxLayout()

        buy = QPushButton("Buy a licence…")
        buy.clicked.connect(lambda: self._open(self.gate.config.purchase_url))
        links.addWidget(buy)

        if self.gate.config.account_url:
            manage = QPushButton("Manage my licences…")
            manage.clicked.connect(lambda: self._open(self.gate.config.account_url))
            links.addWidget(manage)

        copy_details = QPushButton("Copy support details")
        copy_details.setToolTip(
            "Copies this machine's identifier and version, which support may ask for."
        )
        copy_details.clicked.connect(self._copy_details)
        links.addWidget(copy_details)

        links.addStretch(1)
        layout.addLayout(links)

        support = QLabel(
            f"Need help? <a href='mailto:{self.gate.config.support_email}'>"
            f"{self.gate.config.support_email}</a>"
        )
        support.setTextFormat(Qt.RichText)
        support.setOpenExternalLinks(True)
        support.setProperty("role", "muted")
        layout.addWidget(support)

        self.buttons = QDialogButtonBox()
        self.activate_button = self.buttons.addButton("Activate", QDialogButtonBox.AcceptRole)
        self.activate_button.setEnabled(False)
        self.activate_button.clicked.connect(self._activate)

        quit_button = self.buttons.addButton("Quit", QDialogButtonBox.RejectRole)
        quit_button.clicked.connect(self.reject)

        layout.addWidget(self.buttons)

    # ------------------------------------------------------------------

    def _on_key_changed(self, text: str) -> None:
        self.activate_button.setEnabled(len(text.strip()) >= 8)

    def _show_message(self, text: str, ok: bool) -> None:
        palette = theme.current()
        colour = palette.success if ok else palette.danger
        self.message.setStyleSheet(f"color:{colour}")
        self.message.setText(text)
        self.message.setVisible(True)

    def _open(self, url: str) -> None:
        if url:
            QDesktopServices.openUrl(QUrl(url))

    def _copy_details(self) -> None:
        details = (
            f"401K Finder Pro {__version__}\n"
            f"Machine ID: {machine_fingerprint()}\n"
        )
        QGuiApplication.clipboard().setText(details)
        self._show_message("Support details copied to the clipboard.", ok=True)

    # ------------------------------------------------------------------

    def _activate(self) -> None:
        key = self.key_input.text().strip()

        if len(key) < 8:
            return

        self.activate_button.setEnabled(False)
        self.key_input.setEnabled(False)
        self._show_message("Contacting the licence server…", ok=True)

        worker = _ActivationWorker(self.gate, key, self)
        worker.completed.connect(self._on_completed)
        worker.finished.connect(self._clear_worker)

        self._worker = worker
        worker.start()

    def _clear_worker(self) -> None:
        self._worker = None

    def _on_completed(self, result: object) -> None:
        outcome: ActivationResult = result  # type: ignore[assignment]

        self.key_input.setEnabled(True)
        self.activate_button.setEnabled(True)

        if outcome.ok:
            self.activated = True
            QMessageBox.information(
                self,
                "Activated",
                "Thank you — 401K Finder Pro is activated on this computer.",
            )
            self.accept()
            return

        if outcome.state is LicenseState.SEAT_LIMIT:
            self._show_message(
                f"{outcome.message}\n\nRelease a machine you no longer use, "
                f"or contact {self.gate.config.support_email}.",
                ok=False,
            )
        else:
            self._show_message(outcome.message, ok=False)

    def closeEvent(self, event) -> None:  # noqa: ANN001, N802
        if self._worker is not None and self._worker.isRunning():
            self._worker.wait(5000)
        event.accept()


def require_license(gate: LicenseGate, parent: QWidget | None = None) -> bool:
    """
    Ensure the application is licensed, prompting if it is not.

    Returns True when the application may run. Called at start-up, before the
    main window is built.
    """

    status = gate.status()

    if status.allows_use:
        return True

    if status.state is LicenseState.REVOKED:
        QMessageBox.warning(
            parent,
            "Licence no longer valid",
            f"{status.message}\n\nIf you believe this is a mistake, contact "
            f"{gate.config.support_email}.",
        )

    dialog = ActivationDialog(gate, parent)
    dialog.exec()

    return dialog.activated
