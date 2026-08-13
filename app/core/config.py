from __future__ import annotations

from pathlib import Path

from platformdirs import user_data_dir


APP_NAME = "401K Finder Pro"


def get_app_data_dir() -> Path:
    """
    Return the platform-specific application data directory.

    The directory is created when requested.
    """
    path = Path(user_data_dir(APP_NAME))
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_database_dir() -> Path:
    """Return the local database directory."""
    path = get_app_data_dir() / "database"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_data_dir() -> Path:
    """Return the local DOL data directory."""
    path = get_app_data_dir() / "dol_data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_download_dir() -> Path:
    """Return the temporary/download directory."""
    path = get_app_data_dir() / "downloads"
    path.mkdir(parents=True, exist_ok=True)
    return path


def get_log_dir() -> Path:
    """Return the application log directory."""
    path = get_app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


DATABASE_PATH = get_database_dir() / "401k_finder.sqlite3"