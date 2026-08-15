from __future__ import annotations

import zipfile
from pathlib import Path

from app.core.exceptions import ArchiveError
from app.core.logging import get_logger

logger = get_logger(__name__)

#: Refuse to extract an archive that expands to more than this. DOL archives are
#: large but bounded; a ratio far outside that range means a malformed or hostile
#: file, and extracting it would fill the user's disk.
MAX_COMPRESSION_RATIO = 200
MAX_EXTRACTED_BYTES = 200 * 1024**3


def _is_safe_member(name: str, destination: Path) -> bool:
    """Reject absolute paths and anything that escapes the destination."""

    member = Path(name)

    if member.is_absolute() or member.drive:
        return False
    if any(part == ".." for part in member.parts):
        return False

    resolved = (destination / member).resolve()
    return resolved == destination or destination in resolved.parents


def inspect_zip(archive: Path) -> tuple[int, int]:
    """Return ``(compressed_size, uncompressed_size)`` without extracting."""

    with zipfile.ZipFile(archive, "r") as handle:
        compressed = sum(info.compress_size for info in handle.infolist())
        uncompressed = sum(info.file_size for info in handle.infolist())

    return compressed, uncompressed


def safe_extract_zip(archive: Path, destination: Path) -> list[Path]:
    """
    Extract a ZIP archive, rejecting unsafe members before writing anything.

    Every member is checked first so a malicious archive cannot write a few
    good files and then escape the destination on a later entry.
    """

    if not archive.exists():
        raise ArchiveError(f"Archive does not exist: {archive}")

    if not zipfile.is_zipfile(archive):
        raise ArchiveError(f"Not a valid ZIP archive: {archive}")

    destination.mkdir(parents=True, exist_ok=True)
    resolved_destination = destination.resolve()

    extracted: list[Path] = []

    try:
        with zipfile.ZipFile(archive, "r") as handle:
            members = handle.infolist()

            compressed = sum(info.compress_size for info in members) or 1
            uncompressed = sum(info.file_size for info in members)

            if uncompressed > MAX_EXTRACTED_BYTES:
                raise ArchiveError(
                    f"{archive.name} expands to {uncompressed / 1024**3:.1f} GB, "
                    f"which exceeds the {MAX_EXTRACTED_BYTES / 1024**3:.0f} GB limit."
                )

            if uncompressed / compressed > MAX_COMPRESSION_RATIO:
                raise ArchiveError(
                    f"{archive.name} has an implausible compression ratio "
                    f"({uncompressed / compressed:.0f}:1) and was not extracted."
                )

            for info in members:
                if not _is_safe_member(info.filename, resolved_destination):
                    raise ArchiveError(
                        f"Unsafe path in {archive.name}: {info.filename}"
                    )

            for info in members:
                if info.is_dir():
                    continue

                handle.extract(info, resolved_destination)
                extracted.append(resolved_destination / info.filename)

    except zipfile.BadZipFile as exc:
        raise ArchiveError(f"Corrupt ZIP archive: {archive}") from exc
    except OSError as exc:
        raise ArchiveError(f"Unable to extract {archive}: {exc}") from exc

    logger.info("Extracted %s file(s) from %s", len(extracted), archive.name)

    return extracted
