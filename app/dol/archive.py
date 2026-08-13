from __future__ import annotations

import zipfile
from pathlib import Path


class ArchiveError(Exception):
    """Raised when a DOL archive cannot be processed."""


def safe_extract_zip(
    archive: Path,
    destination: Path,
) -> list[Path]:
    """
    Safely extract a ZIP archive.

    Path traversal is explicitly rejected.
    """

    if not archive.exists():
        raise ArchiveError(
            f"Archive does not exist: {archive}"
        )

    if not zipfile.is_zipfile(archive):
        raise ArchiveError(
            f"Not a valid ZIP archive: {archive}"
        )

    destination.mkdir(
        parents=True,
        exist_ok=True,
    )

    extracted: list[Path] = []

    destination_resolved = destination.resolve()

    try:
        with zipfile.ZipFile(archive, "r") as zip_file:
            for member in zip_file.infolist():
                member_path = Path(member.filename)

                if member_path.is_absolute():
                    raise ArchiveError(
                        f"Unsafe absolute path in archive: "
                        f"{member.filename}"
                    )

                target = (
                    destination_resolved / member_path
                ).resolve()

                if (
                    target != destination_resolved
                    and destination_resolved
                    not in target.parents
                ):
                    raise ArchiveError(
                        f"Unsafe path in archive: "
                        f"{member.filename}"
                    )

            for member in zip_file.infolist():
                zip_file.extract(
                    member,
                    destination_resolved,
                )

                extracted.append(
                    destination_resolved
                    / member.filename
                )

    except zipfile.BadZipFile as exc:
        raise ArchiveError(
            f"Corrupt ZIP archive: {archive}"
        ) from exc
    except OSError as exc:
        raise ArchiveError(
            f"Unable to extract archive: {archive}"
        ) from exc

    return extracted