"""
Moving the data to another drive without losing it.

The database is the whole point of the exercise and it can be hundreds of
gigabytes, so this is written to fail safely rather than quickly:

* the target is checked **before** anything is touched, so a FAT32 stick or a
  read-only mount is refused while the data is still where it was;
* every open connection is closed first, because moving a SQLite file out from
  under a live handle is how a database gets truncated;
* the pointer is written **after** the move succeeds, so an interruption leaves
  the application still looking at the old location, which still has the data;
* the move is a move, not a copy, so a drive with just enough room works.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from app.core import storage
from app.core.config import get_app_data_dir, get_storage_dir
from app.core.logging import get_logger

logger = get_logger(__name__)

#: (directory being moved, position, total)
Progress = Callable[[str, int, int], None]


@dataclass(slots=True)
class RelocationResult:
    source: Path
    target: Path

    moved: list[str] = field(default_factory=list)
    bytes_moved: int = 0

    def summary(self) -> str:
        if not self.moved:
            return f"Storage location set to {self.target}. There was no data to move."

        return (
            f"Moved {', '.join(self.moved)} "
            f"({storage.format_bytes(self.bytes_moved)}) to {self.target}."
        )


class RelocationError(RuntimeError):
    """The move cannot proceed, and nothing has been changed."""


def current_location() -> Path:
    """Where the bulk data lives now, without insisting the drive is present."""

    return get_storage_dir(require=False)


def plan_move(target: Path, *, move_existing: bool = True) -> tuple[storage.StorageInfo, int]:
    """
    Check a target and report what moving there would involve.

    Returns the inspection and the number of bytes that would be moved, so a
    caller can confirm before starting something that may take an hour.
    """

    source = current_location()
    info = storage.inspect(Path(target).expanduser())

    if not move_existing or not source.is_dir():
        return info, 0

    return info, storage.managed_size(source)


def relocate(
    target: Path,
    *,
    move_existing: bool = True,
    progress: Progress | None = None,
) -> RelocationResult:
    """
    Point the application at ``target``, optionally taking the data along.

    Raises :class:`RelocationError` before touching anything if the target is
    unusable.
    """

    source = current_location()
    destination = Path(target).expanduser().resolve()

    if source.resolve() == destination:
        raise RelocationError("That is already the storage location.")

    info = storage.inspect(destination, create=True)

    if info.blockers:
        raise RelocationError(" ".join(item.message for item in info.blockers))

    if not info.usable:
        raise RelocationError(f"{destination} cannot be used for storage.")

    payload = storage.managed_size(source) if (move_existing and source.is_dir()) else 0

    # A cross-volume move copies then deletes, so the target needs room for the
    # payload. Checking all of it is the conservative call, and the failure it
    # prevents is a half-moved database.
    cross_volume = payload and not storage.is_same_volume(source, destination)

    if cross_volume and info.free_bytes < payload:
        raise RelocationError(
            f"{destination} has {storage.format_bytes(info.free_bytes)} free but "
            f"{storage.format_bytes(payload)} needs moving. Free up space, or "
            f"choose a location with more room."
        )

    # Release the database file. Moving it while a connection is open is how a
    # SQLite database gets truncated, and on Windows it simply fails.
    from app.database.engine import dispose_engine
    from app.database.session import reset_session_factory

    dispose_engine()
    reset_session_factory()

    result = RelocationResult(source=source, target=destination, bytes_moved=payload)

    if payload or move_existing:
        try:
            result.moved = storage.relocate(source, destination, progress=progress)
        except OSError as exc:
            raise RelocationError(
                f"The move failed part-way: {exc}\n\n"
                f"The storage location has not been changed, so the application "
                f"still points at {source}. Check both locations before retrying."
            ) from exc

    # Written last, so an interruption above leaves the application looking at
    # the old location -- which is where the data still is.
    storage.write_location(get_app_data_dir(), destination)

    logger.info("Storage relocated from %s to %s", source, destination)
    return result


def revert_to_internal(*, move_existing: bool = True, progress: Progress | None = None):
    """Move the data back beside the application and forget the pointer."""

    home = get_app_data_dir()
    source = current_location()

    if source.resolve() == home.resolve():
        storage.clear_location(home)
        return RelocationResult(source=source, target=home)

    result = relocate(home, move_existing=move_existing, progress=progress)
    storage.clear_location(home)

    return result
