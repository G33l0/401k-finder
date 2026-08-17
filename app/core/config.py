from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path

from platformdirs import user_data_dir

APP_NAME = "401K Finder Pro"

#: Set this to run against a scratch directory, which is how the test suite and
#: the portable Windows build keep their data beside the executable.
DATA_DIR_ENV_VAR = "FINDER_401K_DATA_DIR"


def get_app_data_dir() -> Path:
    """Return the application data directory, creating it on first use."""

    override = os.environ.get(DATA_DIR_ENV_VAR)

    # appauthor=False matters on Windows: passing an author name nests the data
    # under %LOCALAPPDATA%\<author>\<appname>, which with an author equal to the
    # application name produced "401K Finder Pro\401K Finder Pro". Every
    # document refers to a single folder, so keep it that way.
    path = (
        Path(override).expanduser()
        if override
        else Path(user_data_dir(APP_NAME, appauthor=False))
    )
    path.mkdir(parents=True, exist_ok=True)
    return path


#: Set to keep the bulk data somewhere other than the application folder --
#: normally an external or USB drive. Overrides the stored pointer, which is
#: what makes it useful for a portable build or a scripted run.
STORAGE_DIR_ENV_VAR = "FINDER_401K_STORAGE_DIR"


class StorageUnavailable(RuntimeError):
    """
    The configured storage location is not there.

    Raised rather than quietly falling back, because the fallback would create
    an empty database at the mount point and present it as an empty search
    result -- which to somebody whose external drive is merely unplugged looks
    exactly like losing everything.
    """

    def __init__(self, path: Path) -> None:
        self.path = path
        super().__init__(
            f"The data folder {path} is not available. If it is on a removable "
            f"drive, connect it and start the application again. The drive letter "
            f"may also have changed."
        )


def get_storage_dir(*, require: bool = True) -> Path:
    """
    Return where the bulk data lives: database, downloads, extracted CSVs.

    Defaults to the application folder. A seventeen-year archive runs to
    hundreds of gigabytes, so it can be pointed at another drive instead --
    see :mod:`app.core.storage`.

    Settings, logs and the licence deliberately do not move. They are tiny,
    they are per-machine, and they have to be readable before anyone knows
    whether the other drive is connected.
    """

    from app.core import storage

    override = os.environ.get(STORAGE_DIR_ENV_VAR)
    configured = (
        Path(override).expanduser() if override else storage.read_location(get_app_data_dir())
    )

    if configured is None:
        return get_app_data_dir()

    if not configured.is_dir():
        if require:
            raise StorageUnavailable(configured)
        return configured

    try:
        configured.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise StorageUnavailable(configured) from exc

    return configured


def _subdirectory(name: str) -> Path:
    path = get_storage_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def _local_subdirectory(name: str) -> Path:
    path = get_app_data_dir() / name
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_database_dir() -> Path:
    return _subdirectory("database")


def get_data_dir() -> Path:
    """Extracted DOL CSV files, organised by form year and dataset."""

    return _subdirectory("dol_data")


def get_download_dir() -> Path:
    """Downloaded ZIP archives, kept so a re-import needs no re-download."""

    return _subdirectory("downloads")


def get_export_dir() -> Path:
    return _subdirectory("exports")


def get_log_dir() -> Path:
    """Always local: a log about an unreachable drive cannot live on it."""

    return _local_subdirectory("logs")


def get_database_path() -> Path:
    return get_database_dir() / "401k_finder.sqlite3"


def get_settings_path() -> Path:
    return get_app_data_dir() / "settings.json"


@dataclass(slots=True)
class Settings:
    """User-adjustable settings, persisted as JSON beside the database."""

    #: Form years to work with by default.
    form_years: list[int] = field(default_factory=lambda: [2023])
    #: "Latest" (one row per plan year) or "All" (every filing received).
    release: str = "Latest"
    #: Restrict syncs to the datasets that carry provider information.
    core_datasets_only: bool = True
    #: Keep downloaded ZIP archives after a successful import.
    keep_archives: bool = True
    #: Keep extracted CSV files after a successful import.
    keep_extracted: bool = False
    #: Rows buffered before each database flush during import.
    import_batch_size: int = 5000
    #: Maximum search results returned to the UI.
    search_limit: int = 200
    #: Seconds before a download request is abandoned.
    download_timeout: float = 120.0
    #: Exclude welfare-only plans from search results.
    retirement_plans_only: bool = True
    #: Colour scheme: "light", "dark" or "hacker". An unknown value falls back
    #: to the default rather than failing, so hand-edited settings cannot stop
    #: the application starting.
    theme: str = "light"

    @classmethod
    def load(cls, path: Path | None = None) -> Settings:
        """Load settings, falling back to defaults for anything unreadable."""

        target = path or get_settings_path()

        if not target.exists():
            return cls()

        try:
            raw = json.loads(target.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return cls()

        if not isinstance(raw, dict):
            return cls()

        known = set(cls.__dataclass_fields__)
        return cls(**{key: value for key, value in raw.items() if key in known})

    def save(self, path: Path | None = None) -> Path:
        target = path or get_settings_path()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(asdict(self), indent=2) + "\n", encoding="utf-8")
        return target


def dataset_directory(form_year: int, dataset: str) -> Path:
    """Return where a dataset's extracted CSV files live."""

    path = get_data_dir() / str(form_year) / dataset.upper()
    path.mkdir(parents=True, exist_ok=True)
    return path
