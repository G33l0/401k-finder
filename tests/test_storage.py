"""
External and removable storage.

The failures these guard against are the expensive kind: a database truncated
mid-move, an empty database silently created at the mount point of a drive that
is merely unplugged, or a six-hour import that dies on FAT32's 4 GB file limit.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from app.core import storage
from app.core.config import STORAGE_DIR_ENV_VAR, StorageUnavailable, get_storage_dir

# ----------------------------------------------------------------------
# Reading a location
# ----------------------------------------------------------------------


def test_inspect_does_not_create_the_directory(tmp_path: Path) -> None:
    """
    The check that answers "is the drive there?" must not make it so.

    An earlier version created the folder, which meant an unplugged drive
    inspected as fine and the application then built an empty database at the
    mount point.
    """

    missing = tmp_path / "not-plugged-in"

    info = storage.inspect(missing)

    assert not missing.exists()
    assert not info.exists


def test_inspect_can_create_when_asked(tmp_path: Path) -> None:
    target = tmp_path / "new-folder"

    info = storage.inspect(target, create=True)

    assert target.is_dir()
    assert info.exists and info.usable


def test_inspect_blocks_a_path_whose_parent_is_gone(tmp_path: Path) -> None:
    info = storage.inspect(tmp_path / "gone" / "deeper", create=True)

    assert not info.usable
    assert info.blockers
    assert "not available" in info.blockers[0].message


def test_inspect_blocks_a_read_only_location(tmp_path: Path) -> None:
    if os.geteuid() == 0:  # pragma: no cover - root ignores the mode bits
        pytest.skip("running as root, which can write to a read-only directory")

    target = tmp_path / "locked"
    target.mkdir()
    target.chmod(0o500)

    try:
        info = storage.inspect(target)
    finally:
        target.chmod(0o700)

    assert not info.writable
    assert not info.usable
    assert any("cannot be written to" in item.message for item in info.blockers)


def test_fat32_is_refused_outright(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """
    A form year's database passes 4 GB, so FAT32 fails part-way through an
    import with a disk-full error that is nothing of the kind. Refuse it up
    front rather than warn.
    """

    monkeypatch.setattr(storage, "volume_details", lambda _p: ("FAT32", True, False))

    info = storage.inspect(tmp_path)

    assert not info.usable
    assert any("4 GB" in item.message for item in info.blockers)
    assert any("exFAT" in item.message for item in info.blockers)


@pytest.mark.parametrize("name", ["FAT32", "vfat", "msdos", "fat"])
def test_every_fat_spelling_is_caught(
    name: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(storage, "volume_details", lambda _p: (name, True, False))

    assert storage.inspect(tmp_path).blockers


def test_a_network_location_warns_but_is_allowed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(storage, "volume_details", lambda _p: ("nfs4", False, True))

    info = storage.inspect(tmp_path)

    assert info.usable
    assert not info.supports_wal
    assert any("network location" in item.message for item in info.warnings)


def test_a_removable_drive_is_a_note_not_a_warning(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(storage, "volume_details", lambda _p: ("exfat", True, False))

    info = storage.inspect(tmp_path)

    assert info.usable
    assert info.removable
    assert not info.blockers
    assert not info.warnings or all(
        "network" not in item.message for item in info.warnings
    )


def test_space_is_measured_against_the_years_asked_for(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    import shutil

    class Usage:
        total = 400 * storage.GIB
        free = 200 * storage.GIB
        used = 200 * storage.GIB

    monkeypatch.setattr(shutil, "disk_usage", lambda _p: Usage)

    roomy = storage.inspect(tmp_path, for_years=3)
    cramped = storage.inspect(tmp_path, for_years=17)

    assert not roomy.warnings
    assert any("17 full" in item.message for item in cramped.warnings)
    assert cramped.usable  # a warning, not a refusal


# ----------------------------------------------------------------------
# The pointer
# ----------------------------------------------------------------------


def test_pointer_round_trips(tmp_path: Path) -> None:
    home = tmp_path / "app"
    home.mkdir()
    drive = tmp_path / "drive"

    assert storage.read_location(home) is None

    storage.write_location(home, drive)
    assert storage.read_location(home) == drive

    storage.clear_location(home)
    assert storage.read_location(home) is None


def test_pointer_lives_with_the_application_not_on_the_drive(tmp_path: Path) -> None:
    """The setting that says where the data is cannot live where the data is."""

    home = tmp_path / "app"
    home.mkdir()
    drive = tmp_path / "drive"
    drive.mkdir()

    storage.write_location(home, drive)

    assert (home / storage.POINTER_FILE).is_file()
    assert not (drive / storage.POINTER_FILE).exists()


def test_a_corrupt_pointer_falls_back_rather_than_refusing_to_start(
    tmp_path: Path,
) -> None:
    home = tmp_path / "app"
    home.mkdir()
    (home / storage.POINTER_FILE).write_text("{ this is not json", encoding="utf-8")

    assert storage.read_location(home) is None


def test_an_empty_pointer_path_means_unset(tmp_path: Path) -> None:
    home = tmp_path / "app"
    home.mkdir()
    (home / storage.POINTER_FILE).write_text(json.dumps({"path": "  "}), encoding="utf-8")

    assert storage.read_location(home) is None


# ----------------------------------------------------------------------
# get_storage_dir
# ----------------------------------------------------------------------


def test_missing_storage_raises_rather_than_creating(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    The whole point of StorageUnavailable: an unplugged drive must say so, not
    produce an empty database that looks like the data was lost.
    """

    missing = tmp_path / "unplugged"
    monkeypatch.setenv(STORAGE_DIR_ENV_VAR, str(missing))

    with pytest.raises(StorageUnavailable) as caught:
        get_storage_dir()

    assert caught.value.path == missing
    assert "connect it" in str(caught.value).lower()
    assert not missing.exists()


def test_storage_dir_can_report_without_insisting(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The UI has to name the drive it cannot reach, so require=False returns it."""

    missing = tmp_path / "unplugged"
    monkeypatch.setenv(STORAGE_DIR_ENV_VAR, str(missing))

    assert get_storage_dir(require=False) == missing


def test_the_environment_override_wins(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    drive = tmp_path / "drive"
    drive.mkdir()
    monkeypatch.setenv(STORAGE_DIR_ENV_VAR, str(drive))

    assert get_storage_dir() == drive


# ----------------------------------------------------------------------
# The journal mode
# ----------------------------------------------------------------------


def test_network_paths_drop_out_of_wal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """WAL needs a shared-memory file, which network filesystems do not provide."""

    from app.database import engine as engine_module

    monkeypatch.setattr(storage, "volume_details", lambda _p: ("cifs", False, True))
    assert engine_module.journal_mode_for(tmp_path / "db.sqlite3") == "DELETE"


def test_a_usb_drive_keeps_wal(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """A directly connected drive is an ordinary filesystem; no need to slow down."""

    from app.database import engine as engine_module

    monkeypatch.setattr(storage, "volume_details", lambda _p: ("exfat", True, False))
    assert engine_module.journal_mode_for(tmp_path / "db.sqlite3") == "WAL"


def test_undetectable_volume_keeps_wal(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def explode(_path):  # noqa: ANN001, ANN202
        raise OSError("no /proc/mounts here")

    from app.database import engine as engine_module

    monkeypatch.setattr(storage, "volume_details", explode)
    assert engine_module.journal_mode_for(tmp_path / "db.sqlite3") == "WAL"


# ----------------------------------------------------------------------
# Moving data
# ----------------------------------------------------------------------


def _populate(root: Path) -> None:
    for name in storage.MANAGED_DIRECTORIES:
        directory = root / name
        directory.mkdir(parents=True)
        (directory / f"{name}.bin").write_bytes(b"x" * 1024)

    (root / "database" / "nested").mkdir()
    (root / "database" / "nested" / "deep.bin").write_bytes(b"y" * 512)

    # Local-only things that must be left exactly where they are.
    (root / "settings.json").write_text("{}", encoding="utf-8")
    (root / "logs").mkdir()
    (root / "logs" / "app.log").write_text("hello", encoding="utf-8")


def test_managed_size_counts_only_what_moves(tmp_path: Path) -> None:
    _populate(tmp_path)

    expected = 1024 * len(storage.MANAGED_DIRECTORIES) + 512
    assert storage.managed_size(tmp_path) == expected


def test_relocate_moves_the_data_and_leaves_the_local_files(tmp_path: Path) -> None:
    source = tmp_path / "internal"
    target = tmp_path / "drive"
    source.mkdir()
    _populate(source)

    moved = storage.relocate(source, target)

    assert sorted(moved) == sorted(storage.MANAGED_DIRECTORIES)
    assert (target / "database" / "nested" / "deep.bin").read_bytes() == b"y" * 512
    assert not (source / "database").exists()

    # Settings and logs are per-machine and stay behind.
    assert (source / "settings.json").is_file()
    assert (source / "logs" / "app.log").is_file()
    assert not (target / "settings.json").exists()


def test_relocate_to_the_same_place_is_a_no_op(tmp_path: Path) -> None:
    _populate(tmp_path)

    assert storage.relocate(tmp_path, tmp_path) == []
    assert (tmp_path / "database" / "database.bin").is_file()


def test_relocate_merges_into_a_half_finished_target(tmp_path: Path) -> None:
    """
    An interrupted move leaves some directories already across. Refusing would
    strand the user with data in two places and no way to finish.
    """

    source = tmp_path / "internal"
    target = tmp_path / "drive"
    source.mkdir()
    _populate(source)

    (target / "database").mkdir(parents=True)
    (target / "database" / "leftover.bin").write_bytes(b"z")

    storage.relocate(source, target)

    assert (target / "database" / "leftover.bin").is_file()
    assert (target / "database" / "database.bin").is_file()
    assert not (source / "database").exists()


def test_relocate_reports_progress(tmp_path: Path) -> None:
    source = tmp_path / "internal"
    source.mkdir()
    _populate(source)

    seen: list[tuple[str, int, int]] = []
    storage.relocate(source, tmp_path / "drive", progress=lambda *args: seen.append(args))

    assert [item[0] for item in seen] == list(storage.MANAGED_DIRECTORIES)
    assert seen[-1][1] == seen[-1][2] == len(storage.MANAGED_DIRECTORIES)


# ----------------------------------------------------------------------
# The relocation service
# ----------------------------------------------------------------------


def test_plan_move_refuses_nothing_and_reports_the_payload(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.services import relocate as service

    source = tmp_path / "internal"
    source.mkdir()
    _populate(source)
    monkeypatch.setattr(service, "current_location", lambda: source)

    info, payload = service.plan_move(tmp_path / "drive")

    assert payload == storage.managed_size(source)
    assert not (tmp_path / "drive").exists()  # planning creates nothing
    assert not info.exists


def test_relocate_service_refuses_fat32_before_touching_anything(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.services import relocate as service

    source = tmp_path / "internal"
    source.mkdir()
    _populate(source)
    target = tmp_path / "stick"
    target.mkdir()

    monkeypatch.setattr(service, "current_location", lambda: source)
    monkeypatch.setattr(storage, "volume_details", lambda _p: ("FAT32", True, False))

    with pytest.raises(service.RelocationError, match="4 GB"):
        service.relocate(target)

    # Nothing moved, nothing pointed anywhere new.
    assert (source / "database" / "database.bin").is_file()
    assert not (target / "database").exists()


def test_relocate_service_refuses_when_the_target_is_too_small(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.services import relocate as service

    source = tmp_path / "internal"
    source.mkdir()
    _populate(source)
    target = tmp_path / "drive"

    monkeypatch.setattr(service, "current_location", lambda: source)
    monkeypatch.setattr(storage, "is_same_volume", lambda _a, _b: False)
    monkeypatch.setattr(storage, "free_space", lambda _p: 1)

    def tiny(path, **kwargs):  # noqa: ANN001, ANN003
        info = storage.StorageInfo(path=Path(path), exists=True, writable=True)
        info.free_bytes = 1
        info.total_bytes = 1024
        Path(path).mkdir(parents=True, exist_ok=True)
        return info

    monkeypatch.setattr(storage, "inspect", tiny)

    with pytest.raises(service.RelocationError, match="needs moving"):
        service.relocate(target)

    assert (source / "database" / "database.bin").is_file()


def test_relocate_service_writes_the_pointer_only_after_the_move(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    Order matters: an interruption must leave the application looking at the old
    location, which is where the data still is.
    """

    from app.services import relocate as service

    home = tmp_path / "app"
    home.mkdir()
    source = tmp_path / "internal"
    source.mkdir()
    _populate(source)
    target = tmp_path / "drive"

    monkeypatch.setattr(service, "current_location", lambda: source)
    monkeypatch.setattr(service, "get_app_data_dir", lambda: home)

    def explode(*_args, **_kwargs):  # noqa: ANN002, ANN003
        raise OSError("the drive was pulled out")

    monkeypatch.setattr(storage, "relocate", explode)

    with pytest.raises(service.RelocationError, match="part-way"):
        service.relocate(target)

    assert storage.read_location(home) is None
    assert (source / "database" / "database.bin").is_file()


def test_relocate_service_moves_and_points(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.services import relocate as service

    home = tmp_path / "app"
    home.mkdir()
    source = tmp_path / "internal"
    source.mkdir()
    _populate(source)
    target = tmp_path / "drive"

    monkeypatch.setattr(service, "current_location", lambda: source)
    monkeypatch.setattr(service, "get_app_data_dir", lambda: home)

    result = service.relocate(target)

    assert storage.read_location(home) == target.resolve()
    assert (target / "database" / "database.bin").is_file()
    assert sorted(result.moved) == sorted(storage.MANAGED_DIRECTORIES)
    assert "Moved" in result.summary()


def test_relocate_service_refuses_the_current_location(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.services import relocate as service

    source = tmp_path / "internal"
    source.mkdir()
    monkeypatch.setattr(service, "current_location", lambda: source)

    with pytest.raises(service.RelocationError, match="already"):
        service.relocate(source)


def test_revert_to_internal_clears_the_pointer(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    from app.services import relocate as service

    home = tmp_path / "app"
    home.mkdir()
    drive = tmp_path / "drive"
    drive.mkdir()
    _populate(drive)

    storage.write_location(home, drive)
    monkeypatch.setattr(service, "current_location", lambda: drive)
    monkeypatch.setattr(service, "get_app_data_dir", lambda: home)

    service.revert_to_internal()

    assert storage.read_location(home) is None
    assert (home / "database" / "database.bin").is_file()


# ----------------------------------------------------------------------
# Formatting
# ----------------------------------------------------------------------


@pytest.mark.parametrize(
    ("count", "expected"),
    [
        (0, "nothing"),
        (900, "900 bytes"),
        (40 * 1024**2, "40.0 MB"),
        (int(1.5 * storage.GIB), "1.5 GB"),
        (250 * storage.GIB, "250 GB"),
        (3 * storage.GIB * 1024, "3.0 TB"),
    ],
)
def test_sizes_read_like_a_person_wrote_them(count: int, expected: str) -> None:
    assert storage.format_bytes(count) == expected


def test_a_full_drive_does_not_claim_room_for_zero_years() -> None:
    info = storage.StorageInfo(path=Path("/x"))
    info.total_bytes = 100 * storage.GIB
    info.free_bytes = 2 * storage.GIB

    assert "not enough room" in info.describe_space()
    assert "0 full form year" not in info.describe_space()
