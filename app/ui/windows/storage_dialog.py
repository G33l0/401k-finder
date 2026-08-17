"""
What to do when the data is on a drive that is not connected.

This runs before the main window exists, and it exists because of one specific
bad outcome: without it the application creates an empty database at the mount
point of the missing drive and opens as though the data were gone. Somebody who
has merely left a USB stick at home would reasonably conclude the software had
destroyed hundreds of gigabytes of work.

So the choice is presented plainly, with the option that loses nothing first.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFileDialog, QMessageBox, QWidget

from app.core.config import StorageUnavailable, get_storage_dir
from app.core.logging import get_logger

logger = get_logger(__name__)


def ensure_storage_available(parent: QWidget | None = None) -> bool:
    """
    Confirm the data folder is reachable, offering a way out when it is not.

    Returns True when the application may continue.
    """

    while True:
        try:
            get_storage_dir()
            return True
        except StorageUnavailable as exc:
            logger.warning("Storage unavailable at %s", exc.path)

            if not _offer_choices(parent, exc):
                return False


def _offer_choices(parent: QWidget | None, exc: StorageUnavailable) -> bool:
    """Ask what to do. Returns True to re-check, False to quit."""

    from app.services.relocate import RelocationError, revert_to_internal

    box = QMessageBox(parent)
    box.setIcon(QMessageBox.Warning)
    box.setWindowTitle("The data drive is not connected")
    box.setText(
        f"401K Finder Pro keeps its data in:\n\n    {exc.path}\n\n"
        f"That folder is not available right now."
    )
    box.setInformativeText(
        "Nothing has been lost. If the data is on a removable drive, connect it "
        "and choose Try again — note that Windows sometimes gives a drive a "
        "different letter, in which case point the application at its new one."
    )

    retry = box.addButton("Try again", QMessageBox.AcceptRole)
    choose = box.addButton("Choose the folder…", QMessageBox.ActionRole)
    internal = box.addButton("Use internal storage", QMessageBox.ResetRole)
    quit_button = box.addButton("Quit", QMessageBox.RejectRole)

    internal.setToolTip(
        "Start fresh on this computer. The data on the other drive is left "
        "untouched and can be pointed at again later."
    )

    box.setDefaultButton(retry)
    box.exec()

    clicked = box.clickedButton()

    if clicked is quit_button:
        return False

    if clicked is retry:
        return True

    if clicked is choose:
        selected = QFileDialog.getExistingDirectory(
            parent, "Where is the 401K Finder Pro data folder?", str(exc.path.parent)
        )
        if not selected:
            return True

        from pathlib import Path

        from app.core import storage
        from app.core.config import get_app_data_dir

        storage.write_location(get_app_data_dir(), Path(selected))
        return True

    # Internal storage. Only the pointer is cleared -- the data on the other
    # drive is deliberately left where it is.
    try:
        revert_to_internal(move_existing=False)
    except RelocationError as error:
        QMessageBox.warning(parent, "Could not switch", str(error))

    return True
