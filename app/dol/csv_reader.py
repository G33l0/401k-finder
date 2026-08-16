from __future__ import annotations

import csv
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from app.core.exceptions import CSVReadError
from app.dol.normalizer import normalize_column_name

#: Tried in order. DOL files are mostly Windows-1252 with occasional UTF-8 BOMs;
#: latin-1 is last because it decodes any byte and so must never pre-empt a
#: more accurate guess.
ENCODINGS: tuple[str, ...] = ("utf-8-sig", "utf-8", "cp1252", "latin-1")

#: Some Schedule H rows carry free-text fields far larger than the csv module's
#: default 128 KB field limit.
_FIELD_SIZE_LIMIT = 8 * 1024 * 1024


def _raise_field_limit() -> None:
    limit = _FIELD_SIZE_LIMIT
    while limit > 1024:
        try:
            csv.field_size_limit(limit)
            return
        except OverflowError:
            limit //= 2
    csv.field_size_limit(sys.maxsize if sys.maxsize < 2**31 else 2**31 - 1)


_raise_field_limit()


def detect_encoding(path: Path, sample_bytes: int = 1 << 20) -> str:
    """
    Return an encoding that decodes the file, checked against a leading sample.

    A 1 MB sample is enough to surface the non-ASCII characters that separate
    cp1252 from UTF-8 in these files while staying fast on multi-gigabyte CSVs.
    """

    # The handle is closed before returning. Windows refuses to delete a file
    # that is still open, and the sync service deletes these CSVs once the
    # import finishes.
    try:
        with path.open("rb") as handle:
            raw = handle.read(sample_bytes)
    except OSError as exc:
        raise CSVReadError(f"Unable to open CSV file: {path}") from exc

    for encoding in ENCODINGS:
        try:
            raw.decode(encoding)
        except UnicodeDecodeError:
            continue
        return encoding

    raise CSVReadError(f"Unable to determine a supported encoding for: {path}")


def read_header(path: Path) -> tuple[str, ...]:
    """Return the CSV header without reading the rest of the file."""

    encoding = detect_encoding(path)

    try:
        with path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.reader(handle)
            header = next(reader, None)
    except OSError as exc:
        raise CSVReadError(f"Unable to read CSV file: {path}") from exc

    if not header:
        raise CSVReadError(f"CSV file has no header: {path}")

    return tuple(column.strip() for column in header)


def read_csv_rows(
    path: Path,
    normalize_keys: bool = True,
) -> Iterator[tuple[int, dict[str, Any]]]:
    """
    Yield ``(row_number, row)`` pairs, with row numbers matching the file.

    Row numbers start at 2 so they line up with what a spreadsheet shows,
    which matters because they are recorded as evidence.

    Short rows are padded and over-long rows keep their surplus values under a
    ``_EXTRA`` key rather than being dropped: a malformed row in one of these
    files is still worth importing, and silently discarding it would leave a
    plan looking like it has no provider.
    """

    if not path.exists():
        raise CSVReadError(f"CSV file does not exist: {path}")
    if not path.is_file():
        raise CSVReadError(f"CSV path is not a file: {path}")

    encoding = detect_encoding(path)

    try:
        with path.open("r", encoding=encoding, newline="") as handle:
            reader = csv.reader(handle)

            try:
                header = next(reader)
            except StopIteration:
                raise CSVReadError(f"CSV file has no header: {path}") from None

            columns = [column.strip() for column in header]
            if normalize_keys:
                columns = [normalize_column_name(column) for column in columns]

            for index, column in enumerate(columns):
                if not column:
                    columns[index] = f"COLUMN_{index + 1}"

            width = len(columns)

            for row_number, values in enumerate(reader, start=2):
                if not values or (len(values) == 1 and not values[0].strip()):
                    continue

                row: dict[str, Any] = {}
                for index in range(width):
                    row[columns[index]] = values[index] if index < len(values) else ""

                if len(values) > width:
                    row["_EXTRA"] = values[width:]

                yield row_number, row

    except UnicodeDecodeError as exc:
        raise CSVReadError(f"Unable to decode CSV file: {path}") from exc
    except csv.Error as exc:
        raise CSVReadError(f"Invalid CSV data in {path}: {exc}") from exc
    except OSError as exc:
        raise CSVReadError(f"Unable to read CSV file: {path}") from exc


def count_rows(path: Path) -> int:
    """
    Count data rows, for progress reporting.

    Counts newlines on the raw bytes rather than parsing, so it stays fast on
    the multi-gigabyte files; embedded newlines inside quoted fields make this
    an upper bound rather than an exact count.
    """

    try:
        with path.open("rb") as handle:
            total = sum(chunk.count(b"\n") for chunk in iter(lambda: handle.read(1 << 20), b""))
    except OSError as exc:
        raise CSVReadError(f"Unable to read CSV file: {path}") from exc

    return max(total - 1, 0)


def find_csv_files(directory: Path) -> tuple[Path, ...]:
    """Return every CSV file under a directory, in a stable order."""

    if not directory.exists():
        return ()

    return tuple(sorted(path for path in directory.rglob("*.csv") if path.is_file()))
