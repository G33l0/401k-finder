from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler

from app.core.config import get_log_dir

LOGGER_NAME = "401k_finder"

_configured = False


def configure_logging(level: int = logging.INFO, console: bool = True) -> logging.Logger:
    """Configure application logging. Safe to call repeatedly."""

    global _configured

    logger = logging.getLogger(LOGGER_NAME)

    if _configured:
        return logger

    logger.setLevel(level)
    logger.propagate = False

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-7s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    try:
        file_handler = RotatingFileHandler(
            get_log_dir() / "application.log",
            maxBytes=5 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)
    except OSError:
        pass

    if console:
        console_handler = logging.StreamHandler(stream=sys.stderr)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    if not logger.handlers:
        logger.addHandler(logging.NullHandler())

    _configured = True
    return logger


def get_logger(name: str | None = None) -> logging.Logger:
    """Return a child of the application logger."""

    root = logging.getLogger(LOGGER_NAME)

    if name is None or name == LOGGER_NAME:
        return root

    suffix = name.removeprefix("app.")
    return root.getChild(suffix)
