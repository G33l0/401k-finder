"""Where the bulk data lives, including on an external or USB drive."""

from __future__ import annotations

import os
import shutil
import sys
from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path

POINTER_FILE = "storage.json"

MANAGED_DIRECTORIES: tuple[str, ...] = ("database", "dol_data", "downloads", "exports")

BYTES_PER_FORM_YEAR = 60 * 1024**3

FAT32_MAX_FILE = 4 * 1024**3

GIB = 1024**3


def format_bytes(count: int) -> str:
    """A size a person can read. "0.0 GB" for 40 MB is worse than saying nothing."""

    if count <= 0:
        return "nothing"

    for unit, size in (("TB", GIB * 1024), ("GB", GIB), ("MB", 1024**2), ("KB", 1024)):
        if count >= size:
            value = count / size
            return f"{value:,.0f} {unit}" if value >= 100 else f"{value:,.1f} {unit}"

    return f"{count} bytes"


class Severity(StrEnum):
    BLOCKER = "BLOCKER"
    WARNING = "WARNING"
    NOTE = "NOTE"


@dataclass(frozen=True, slots=True)
class Finding:
    severity: Severity
    message: str

    @property
    def blocks(self) -> bool:
        return self.severity is Severity.BLOCKER


@dataclass(slots=True)
class StorageInfo:
    """What is known about a candidate location."""

    path: Path

    exists: bool = False
    writable: bool = False

    filesystem: str = ""

    removable: bool = False
    network: bool = False

    free_bytes: int = 0
    total_bytes: int = 0

    findings: list[Finding] = field(default_factory=list)

    @property
    def usable(self) -> bool:
        return self.exists and self.writable and not any(f.blocks for f in self.findings)

    @property
    def blockers(self) -> list[Finding]:
        return [item for item in self.findings if item.blocks]

    @property
    def warnings(self) -> list[Finding]:
        return [item for item in self.findings if item.severity is Severity.WARNING]

    @property
    def supports_wal(self) -> bool:
        """Whether SQLite's write-ahead journal will work here."""

        return not self.network

    @property
    def years_that_fit(self) -> int:
        return int(self.free_bytes // BYTES_PER_FORM_YEAR)

    def describe_space(self) -> str:
        if not self.total_bytes:
            return "free space unknown"

        years = self.years_that_fit
        room = (
            f"room for about {years} full form year{'' if years == 1 else 's'}"
            if years
            else "not enough room for a full form year"
        )

        return (
            f"{format_bytes(self.free_bytes)} free of "
            f"{format_bytes(self.total_bytes)}, {room}"
        )

    def describe(self) -> str:
        parts = [str(self.path)]

        if self.filesystem:
            parts.append(self.filesystem)
        if self.network:
            parts.append("network location")
        elif self.removable:
            parts.append("removable drive")

        parts.append(self.describe_space())
        return "  ·  ".join(parts)


def _windows_volume(path: Path) -> tuple[str, bool, bool]:
    """(filesystem name, removable, network) for a Windows path."""

    import ctypes

    root = str(Path(path.anchor or path))
    if not root.endswith("\\"):
        root += "\\"

    kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]

    drive_type = kernel32.GetDriveTypeW(ctypes.c_wchar_p(root))

    name = ctypes.create_unicode_buffer(261)
    filesystem = ctypes.create_unicode_buffer(261)

    ok = kernel32.GetVolumeInformationW(
        ctypes.c_wchar_p(root),
        name,
        ctypes.sizeof(name),
        None,
        None,
        None,
        filesystem,
        ctypes.sizeof(filesystem),
    )

    return (filesystem.value if ok else ""), drive_type == 2, drive_type == 4


def _posix_volume(path: Path) -> tuple[str, bool, bool]:
    """(filesystem name, removable, network) for a POSIX path."""

    remote = {"nfs", "nfs4", "cifs", "smbfs", "smb", "afpfs", "fuse.sshfs", "webdav"}
    removable_roots = ("/media", "/run/media", "/mnt", "/Volumes")

    resolved = path.resolve()
    filesystem = ""
    best = 0

    try:
        with open("/proc/mounts", encoding="utf-8") as handle:
            for line in handle:
                fields = line.split()
                if len(fields) < 3:
                    continue

                mount_point = fields[1].replace("\\040", " ")
                on_this_mount = str(resolved) == mount_point or str(resolved).startswith(
                    mount_point.rstrip("/") + "/"
                )

                if on_this_mount and len(mount_point) >= best:
                    best, filesystem = len(mount_point), fields[2]
    except OSError:
        pass

    is_removable = any(str(resolved).startswith(root) for root in removable_roots)

    return filesystem, is_removable, filesystem.lower() in remote


def volume_details(path: Path) -> tuple[str, bool, bool]:
    """(filesystem, removable, network), empty and False when undetectable."""

    try:
        if sys.platform == "win32":
            return _windows_volume(path)
        return _posix_volume(path)
    except Exception:  # noqa: BLE001 - detection is advisory, never fatal
        return "", False, False


def _probe_writable(path: Path) -> bool:
    """
    Actually write a file. A read-only mount and a full disk both look fine
    until something is written, and finding out during an import is too late.
    """

    probe = path / ".401k-finder-write-test"

    try:
        probe.write_bytes(b"ok")
        probe.unlink()
        return True
    except OSError:
        return False


def inspect(path: Path, *, for_years: int = 0, create: bool = False) -> StorageInfo:
    """Examine a candidate storage location and report what would go wrong."""

    target = Path(path).expanduser()
    info = StorageInfo(path=target)
    info.exists = target.is_dir()

    probe_at = target if info.exists else target.parent

    if not probe_at.is_dir():
        info.findings.append(
            Finding(
                Severity.BLOCKER,
                f"{target} is not available. If this is a removable drive, connect "
                f"it and try again. The drive letter may also have changed.",
            )
        )
        return info

    if create and not info.exists:
        try:
            target.mkdir(parents=True, exist_ok=True)
            info.exists = True
            probe_at = target
        except OSError as exc:
            info.findings.append(
                Finding(Severity.BLOCKER, f"Could not create {target}: {exc}")
            )
            return info

    info.writable = _probe_writable(probe_at)
    if not info.writable:
        info.findings.append(
            Finding(
                Severity.BLOCKER,
                f"{probe_at} cannot be written to. It may be read-only, full, or "
                f"need permissions this account does not have.",
            )
        )

    info.filesystem, info.removable, info.network = volume_details(probe_at)

    try:
        usage = shutil.disk_usage(probe_at)
        info.free_bytes, info.total_bytes = usage.free, usage.total
    except OSError:
        pass

    _check_filesystem(info)
    _check_space(info, for_years)

    return info


def _check_filesystem(info: StorageInfo) -> None:
    name = info.filesystem.upper()

    if name in {"FAT32", "FAT", "MSDOS", "VFAT"}:
        info.findings.append(
            Finding(
                Severity.BLOCKER,
                f"This drive is formatted {info.filesystem}, which cannot hold a "
                f"file larger than {FAT32_MAX_FILE // GIB} GB. A single form year "
                f"passes that, so the database would fail part-way through an "
                f"import. Reformat the drive as exFAT or NTFS first. That erases "
                f"it, so copy anything you need off it beforehand.",
            )
        )

    if info.network:
        info.findings.append(
            Finding(
                Severity.WARNING,
                "This looks like a network location. It will work, but the "
                "database drops to a slower journal mode because the faster one "
                "needs shared memory that network shares do not provide. A "
                "directly connected drive is much faster.",
            )
        )

    if info.removable:
        info.findings.append(
            Finding(
                Severity.NOTE,
                "Removable drive. Connect it before opening the application, and "
                "close the application before ejecting it.",
            )
        )


def _check_space(info: StorageInfo, for_years: int) -> None:
    if not info.total_bytes:
        return

    if for_years:
        needed = for_years * BYTES_PER_FORM_YEAR
        if info.free_bytes < needed:
            info.findings.append(
                Finding(
                    Severity.WARNING,
                    f"{info.free_bytes / GIB:,.0f} GB free, but {for_years} full "
                    f"form year(s) need roughly {needed / GIB:,.0f} GB. About "
                    f"{info.years_that_fit} year(s) would fit.",
                )
            )
        return

    if info.free_bytes < BYTES_PER_FORM_YEAR:
        info.findings.append(
            Finding(
                Severity.WARNING,
                f"Only {info.free_bytes / GIB:,.1f} GB free, less than one full form "
                f"year needs. The employer index is far smaller and would "
                f"still fit.",
            )
        )


def pointer_path(app_dir: Path) -> Path:
    return app_dir / POINTER_FILE


def read_location(app_dir: Path) -> Path | None:
    """The configured storage root, or None when the default is in use."""

    import json

    target = pointer_path(app_dir)

    if not target.is_file():
        return None

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        location = str(data["path"]).strip()
    except (OSError, ValueError, KeyError, TypeError):
        return None

    return Path(location) if location else None


def write_location(app_dir: Path, path: Path) -> Path:
    """Record where the bulk data lives."""

    import json

    target = pointer_path(app_dir)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(
        json.dumps({"path": str(Path(path).expanduser())}, indent=2) + "\n",
        encoding="utf-8",
    )

    return target


def clear_location(app_dir: Path) -> None:
    """Revert to keeping the data with the application."""

    pointer_path(app_dir).unlink(missing_ok=True)


def candidates() -> list[StorageInfo]:
    """Drives worth offering as a storage location."""

    found: list[Path] = []

    if sys.platform == "win32":
        import string

        for letter in string.ascii_uppercase:
            root = Path(f"{letter}:\\")
            if root.exists():
                found.append(root)
    else:
        for parent in ("/media", "/run/media", "/mnt", "/Volumes"):
            base = Path(parent)
            if not base.is_dir():
                continue
            try:
                for entry in sorted(base.iterdir()):
                    if entry.is_dir():
                        nested = [item for item in entry.iterdir() if item.is_dir()]
                        found.extend(nested or [entry])
            except OSError:
                continue

    results = []
    for path in found:
        try:
            results.append(inspect(path))
        except OSError:
            continue

    return results


def managed_size(root: Path) -> int:
    """Bytes currently held in the movable subdirectories."""

    total = 0

    for name in MANAGED_DIRECTORIES:
        directory = root / name
        if not directory.is_dir():
            continue
        for entry in directory.rglob("*"):
            try:
                if entry.is_file():
                    total += entry.stat().st_size
            except OSError:
                continue

    return total


def relocate(
    source_root: Path,
    target_root: Path,
    progress=None,  # noqa: ANN001 - Callable[[str, int, int], None]
) -> list[str]:
    """Move the bulk data from one root to another."""

    source_root = Path(source_root).expanduser()
    target_root = Path(target_root).expanduser()

    if source_root.resolve() == target_root.resolve():
        return []

    target_root.mkdir(parents=True, exist_ok=True)
    moved: list[str] = []

    present = [name for name in MANAGED_DIRECTORIES if (source_root / name).is_dir()]

    for position, name in enumerate(present, start=1):
        source = source_root / name
        destination = target_root / name

        if progress is not None:
            progress(name, position, len(present))

        if destination.exists():
            for entry in source.iterdir():
                final = destination / entry.name
                if final.exists():
                    shutil.rmtree(final) if final.is_dir() else final.unlink()
                shutil.move(str(entry), str(final))
            source.rmdir()
        else:
            shutil.move(str(source), str(destination))

        moved.append(name)

    return moved


def free_space(path: Path) -> int:
    try:
        return shutil.disk_usage(path).free
    except OSError:
        return 0


def is_same_volume(left: Path, right: Path) -> bool:
    """Whether two paths sit on the same device, so a move would be instant."""

    try:
        return os.stat(left).st_dev == os.stat(right).st_dev
    except OSError:
        return False
