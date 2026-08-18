"""The licence key kept on the customer's machine."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path

from app.core.config import get_app_data_dir
from app.core.logging import get_logger
from app.licensing.models import utcnow

logger = get_logger(__name__)

FILENAME = "license.json"


@dataclass(slots=True)
class StoredLicense:
    """What is remembered between runs."""

    key: str
    activated_at: str

    def activated(self) -> datetime | None:
        try:
            return datetime.fromisoformat(self.activated_at)
        except (TypeError, ValueError):
            return None


def license_path() -> Path:
    return get_app_data_dir() / FILENAME


def save(key: str) -> Path:
    """Store a licence key."""

    record = StoredLicense(key=key.strip(), activated_at=utcnow().isoformat())

    target = license_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(asdict(record), indent=2) + "\n", encoding="utf-8")

    return target


def load() -> StoredLicense | None:
    """Read the stored licence, or None if there is not a readable one."""

    target = license_path()

    if not target.exists():
        return None

    try:
        data = json.loads(target.read_text(encoding="utf-8"))
        return StoredLicense(key=str(data["key"]), activated_at=str(data.get("activated_at", "")))
    except (OSError, ValueError, KeyError, TypeError):
        logger.warning("The stored licence could not be read; the key must be entered again.")
        return None


def clear() -> None:
    """Remove the stored licence."""

    license_path().unlink(missing_ok=True)
