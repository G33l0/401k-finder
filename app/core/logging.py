from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.core.config import get_log_dir


LOGGER_NAME = "401k_finder"


def configure_logging() -> logging.Logger:
    """
    Configure application logging.

    Calling this function more than once is safe.
    """
    logger = logging.getLogger(LOGGER_NAME)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    file_handler = RotatingFileHandler(
        get_log_dir() / "application.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    return logger