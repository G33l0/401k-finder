from __future__ import annotations

import csv
from collections.abc import Iterator
from pathlib import Path
from typing import Any


class CSVReadError(Exception):
    """Raised when a CSV file cannot be read."""


ENCODINGS = (
    "utf-8-sig",
    "utf-8",
    "cp1252",
    "latin-1",
)


def detect_encoding(path: Path) -> str:
    """
    Detect a usable encoding from a small sample.

    This is intentionally conservative. If none of the preferred
    encodings works, the caller receives a CSVReadError.
    """

    for encoding in ENCODINGS:
        try:
            with path.open("r", encoding=encoding, newline="") as file:
                file.read(8192)
            return encoding
        except UnicodeDecodeError:
            continue
        except OSError as exc:
            raise CSVReadError(
                f"Unable to open CSV file: {path}"
            ) from exc

    raise CSVReadError(
        f"Unable to determine a supported encoding for: {path}"
    )


def read_csv_rows(
    path: Path,
) -> Iterator[tuple[int, dict[str, Any]]]:
    """
    Yield CSV records as (row_number, dictionary).

    The header is normalized only for whitespace. Original values
    remain untouched.
    """

    if not path.exists():
        raise CSVReadError(f"CSV file does not exist: {path}")

    if not path.is_file():
        raise CSVReadError(f"CSV path is not a file: {path}")

    encoding = detect_encoding(path)

    try:
        with path.open(
            "r",
            encoding=encoding,
            newline="",
        ) as file:
            reader = csv.DictReader(file)

            if not reader.fieldnames:
                raise CSVReadError(
                    f"CSV file has no header: {path}"
                )

            fieldnames = [
                field.strip() if field else ""
                for field in reader.fieldnames
            ]

            if any(not field for field in fieldnames):
                raise CSVReadError(
                    f"CSV file contains an empty column name: {path}"
                )

            reader.fieldnames = fieldnames

            for row_number, row in enumerate(reader, start=2):
                cleaned = {
                    key: value
                    for key, value in row.items()
                    if key is not None
                }

                yield row_number, cleaned

    except UnicodeError as exc:
        raise CSVReadError(
            f"Unable to decode CSV file: {path}"
        ) from exc
    except csv.Error as exc:
        raise CSVReadError(
            f"Invalid CSV data in: {path}"
        ) from exc
    except OSError as exc:
        raise CSVReadError(
            f"Unable to read CSV file: {path}"
        ) from exc