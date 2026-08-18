"""The activation window shown when a build requires a licence."""

from __future__ import annotations

from PySide6.QtCore import Qt, QUrl
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app import __version__
from app.licensing import LicenseGate, LicenseState, machine_fingerprint
from app.ui import resources, theme


def _mailto(gate: LicenseGate, subject: str, body: str) -> str:
    """Build a mailto: link with the machine details already filled in."""

    from urllib.parse import quote

    return (
        f"mailto:{gate.config.support_email}"
        f"?subject={quote(subject)}&body={quote(body)}"
    )


class ActivationDialog(QDialog):
    """Collects a licence key and installs it."""

    def __init__(self, gate: LicenseGate, parent: QWidget | None = None) -> None:
        super().__init__(parent)

        self.gate = gate
        self.activated = False
        self.fingerprint = machine_fingerprint()

        self.setWindowTitle(f"Activate {gate.config.product_name}")
        self.setMinimumWidth(560)

        icon = resources.app_icon()
        if icon is not None:
            self.setWindowIcon(icon)

        self._build()

    def _build(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(12)

        heading = QLabel(
            f"<h2 style='margin:0'>{self.gate.config.product_name} {__version__}</h2>"
        )
        heading.setTextFormat(Qt.RichText)
        layout.addWidget(heading)

        intro = QLabel(
            "Licences are issued by email. Send us the Machine ID below and we will "
            f"reply with a key for this computer.<br><br>"
            f"<b>To buy a licence or ask a question, email "
            f"<a href='mailto:{self.gate.config.support_email}'>"
            f"{self.gate.config.support_email}</a></b>"
        )
        intro.setTextFormat(Qt.RichText)
        intro.setOpenExternalLinks(True)
        intro.setWordWrap(True)
        layout.addWidget(intro)

        machine_row = QHBoxLayout()

        machine_label = QLabel("Machine ID:")
        machine_label.setProperty("role", "muted")
        machine_row.addWidget(machine_label)

        self.machine_field = QLineEdit(self.fingerprint)
        self.machine_field.setReadOnly(True)
        self.machine_field.setCursorPosition(0)
        machine_row.addWidget(self.machine_field, 1)

        layout.addLayout(machine_row)

        buy = QHBoxLayout()

        email_button = QPushButton("Email us for a licence…")
        email_button.setToolTip(
            f"Opens your email program with a message to {self.gate.config.support_email}."
        )
        email_button.clicked.connect(self._request_licence)
        buy.addWidget(email_button)

        copy_button = QPushButton("Copy Machine ID")
        copy_button.clicked.connect(self._copy_machine_id)
        buy.addWidget(copy_button)

        buy.addStretch(1)
        layout.addLayout(buy)

        rule = QFrame()
        rule.setFrameShape(QFrame.HLine)
        rule.setFrameShadow(QFrame.Sunken)
        layout.addWidget(rule)

        entry_label = QLabel("Paste your licence key here:")
        layout.addWidget(entry_label)

        self.key_input = QPlainTextEdit()
        self.key_input.setPlaceholderText(
            "XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX-XXXXXXXX…"
        )
        self.key_input.setFixedHeight(76)
        self.key_input.textChanged.connect(self._on_key_changed)
        layout.addWidget(self.key_input)

        self.message = QLabel()
        self.message.setWordWrap(True)
        self.message.setVisible(False)
        layout.addWidget(self.message)

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

    def _key_text(self) -> str:
        return self.key_input.toPlainText().strip()

    def _on_key_changed(self) -> None:
        self.activate_button.setEnabled(len(self._key_text()) >= 32)

    def _show_message(self, text: str, ok: bool) -> None:
        palette = theme.current()
        colour = palette.success if ok else palette.danger
        self.message.setStyleSheet(f"color:{colour}")
        self.message.setText(text)
        self.message.setVisible(True)

    def _details(self) -> str:
        return (
            f"{self.gate.config.product_name} {__version__}\n"
            f"Machine ID: {self.fingerprint}\n"
        )

    def _copy_machine_id(self) -> None:
        QGuiApplication.clipboard().setText(self.fingerprint)
        self._show_message("Machine ID copied to the clipboard.", ok=True)

    def _request_licence(self) -> None:
        opened = QDesktopServices.openUrl(
            QUrl(
                _mailto(
                    self.gate,
                    f"Licence request: {self.gate.config.product_name}",
                    "Hello,\n\nI would like to buy a licence for "
                    f"{self.gate.config.product_name}.\n\n{self._details()}\n"
                    "Thank you.\n",
                )
            )
        )

        if opened:
            return

        QGuiApplication.clipboard().setText(
            f"To: {self.gate.config.support_email}\n\n{self._details()}"
        )
        self._show_message(
            f"No email program is set up on this computer. The address and your "
            f"Machine ID have been copied to the clipboard. Email them to "
            f"{self.gate.config.support_email} from anywhere.",
            ok=True,
        )

    def _activate(self) -> None:
        result = self.gate.activate(self._key_text())

        if result.ok:
            self.activated = True
            expiry = (
                ""
                if result.expires is None
                else f"\n\nThis licence is valid until {result.expires:%d %B %Y}."
            )
            QMessageBox.information(
                self,
                "Activated",
                f"Thank you. {self.gate.config.product_name} is now activated on this "
                f"computer.{expiry}",
            )
            self.accept()
            return

        if result.state is LicenseState.WRONG_MACHINE:
            self._show_message(
                f"{result.message}\n\nEmail {self.gate.config.support_email} with the "
                f"Machine ID above and we will issue a key for this one.",
                ok=False,
            )
        elif result.state is LicenseState.EXPIRED:
            self._show_message(
                f"{result.message}\n\nEmail {self.gate.config.support_email} to renew.",
                ok=False,
            )
        else:
            self._show_message(result.message, ok=False)


def require_license(gate: LicenseGate, parent: QWidget | None = None) -> bool:
    """Ensure the application is licensed, prompting if it is not."""

    status = gate.status()

    if status.allows_use:
        return True

    dialog = ActivationDialog(gate, parent)

    if status.state in {LicenseState.EXPIRED, LicenseState.WRONG_MACHINE}:
        dialog._show_message(status.message, ok=False)

    dialog.exec()

    return dialog.activated
