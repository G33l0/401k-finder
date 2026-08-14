from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.dol.csv_reader import read_csv_rows
from app.dol.schedules.normalizer import normalize_column_name


@dataclass(slots=True)
class ValidationIssue:
    severity: str
    message: str
    file: str | None = None
    row: int | None = None


@dataclass(slots=True)
class ValidationResult:
    valid: bool
    files_checked: int = 0
    rows_checked: int = 0
    issues: list[ValidationIssue] = field(
        default_factory=list
    )

    def error_count(self) -> int:
        return sum(
            1
            for issue in self.issues
            if issue.severity == "ERROR"
        )

    def warning_count(self) -> int:
        return sum(
            1
            for issue in self.issues
            if issue.severity == "WARNING"
        )


def validate_csv_file(
    path: Path,
    expected_columns: tuple[str, ...] = (),
) -> ValidationResult:
    result = ValidationResult(valid=True)

    try:
        iterator = read_csv_rows(path)
        first_row = next(iterator, None)

        if first_row is None:
            result.valid = False
            result.issues.append(
                ValidationIssue(
                    "ERROR",
                    "CSV contains no data rows.",
                    str(path),
                )
            )
            return result

        result.files_checked = 1

        row_number, row = first_row

        if not row:
            result.valid = False
            result.issues.append(
                ValidationIssue(
                    "ERROR",
                    "First data row is empty.",
                    str(path),
                    row_number,
                )
            )
            return result

        actual = {
            normalize_column_name(key)
            for key in row.keys()
        }

        if not actual:
            result.valid = False
            result.issues.append(
                ValidationIssue(
                    "ERROR",
                    "No usable columns found.",
                    str(path),
                )
            )
            return result

        expected = {
            normalize_column_name(column)
            for column in expected_columns
        }

        missing = expected - actual

        for column in sorted(missing):
            result.issues.append(
                ValidationIssue(
                    "ERROR",
                    f"Missing required column: {column}",
                    str(path),
                )
            )

        result.rows_checked = 1

        for row_number, row in iterator:
            result.rows_checked += 1

            if not row:
                result.issues.append(
                    ValidationIssue(
                        "WARNING",
                        "Empty data row.",
                        str(path),
                        row_number,
                    )
                )

    except Exception as exc:
        result.valid = False
        result.issues.append(
            ValidationIssue(
                "ERROR",
                str(exc),
                str(path),
            )
        )

    result.valid = not any(
        issue.severity == "ERROR"
        for issue in result.issues
    )

    return result


def validate_dataset(
    directory: Path,
) -> ValidationResult:
    result = ValidationResult(valid=True)

    if not directory.exists():
        result.valid = False
        result.issues.append(
            ValidationIssue(
                "ERROR",
                f"Dataset directory does not exist: {directory}",
            )
        )
        return result

    csv_files = sorted(
        directory.rglob("*.csv")
    )

    if not csv_files:
        result.valid = False
        result.issues.append(
            ValidationIssue(
                "ERROR",
                "No CSV files were found.",
                str(directory),
            )
        )
        return result

    for csv_file in csv_files:
        file_result = validate_csv_file(
            csv_file
        )

        result.files_checked += (
            file_result.files_checked
        )
        result.rows_checked += (
            file_result.rows_checked
        )
        result.issues.extend(
            file_result.issues
        )

    result.valid = not any(
        issue.severity == "ERROR"
        for issue in result.issues
    )

    return result