"""
Validate downloaded DOL files against their published layouts.

Validation is layout-driven: a file is compared to the field list DOL published
for that dataset and year. A missing key column is an error because the row
cannot be attached to a filing without it; a missing or unexpected non-key
column is a warning, since DOL does revise layouts and the importer reads by
column name rather than position.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from app.core.exceptions import CSVReadError
from app.dol.csv_reader import find_csv_files, read_header
from app.dol.filing_parser import infer_dataset_from_filename
from app.dol.layouts import get_layout

ERROR = "ERROR"
WARNING = "WARNING"
INFO = "INFO"


@dataclass(slots=True)
class ValidationIssue:
    severity: str
    message: str
    file: str | None = None
    row: int | None = None

    def __str__(self) -> str:
        location = f" [{Path(self.file).name}]" if self.file else ""
        return f"{self.severity}{location}: {self.message}"


@dataclass(slots=True)
class ValidationResult:
    valid: bool = True
    files_checked: int = 0
    issues: list[ValidationIssue] = field(default_factory=list)

    def add(self, severity: str, message: str, file: str | None = None, row: int | None = None) -> None:
        self.issues.append(ValidationIssue(severity, message, file, row))
        if severity == ERROR:
            self.valid = False

    def errors(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == ERROR]

    def warnings(self) -> list[ValidationIssue]:
        return [issue for issue in self.issues if issue.severity == WARNING]

    def error_count(self) -> int:
        return len(self.errors())

    def warning_count(self) -> int:
        return len(self.warnings())

    def merge(self, other: ValidationResult) -> None:
        self.files_checked += other.files_checked
        self.issues.extend(other.issues)
        self.valid = self.valid and other.valid

    def summary(self) -> str:
        state = "valid" if self.valid else "invalid"
        return (
            f"{self.files_checked} file(s) checked: {state}, "
            f"{self.error_count()} error(s), {self.warning_count()} warning(s)"
        )


def validate_csv_file(
    path: Path,
    dataset: str | None = None,
    form_year: int | None = None,
) -> ValidationResult:
    """
    Check one CSV file against the layout DOL published for it.

    When the dataset and year are not supplied they are recovered from the
    filename, which DOL names consistently after the archive.
    """

    result = ValidationResult()

    if dataset is None or form_year is None:
        inferred_dataset, inferred_year = infer_dataset_from_filename(path.name)
        dataset = dataset or inferred_dataset
        form_year = form_year or inferred_year

    try:
        header = read_header(path)
    except CSVReadError as exc:
        result.add(ERROR, str(exc), str(path))
        return result

    result.files_checked = 1

    if not header:
        result.add(ERROR, "File has no header row.", str(path))
        return result

    if dataset is None or form_year is None:
        result.add(
            WARNING,
            "Could not tell which DOL dataset this file is, so its columns were "
            "not checked against a published layout.",
            str(path),
        )
        return result

    layout = get_layout(form_year, dataset)
    if layout is None:
        result.add(
            WARNING,
            f"No vendored layout for {dataset} {form_year}; columns were not checked.",
            str(path),
        )
        return result

    if "ACK_ID" not in {column.strip().upper() for column in header}:
        result.add(
            ERROR,
            "File has no ACK_ID column, so its rows cannot be attached to a filing.",
            str(path),
        )

    missing = layout.missing_from(header)
    if missing:
        preview = ", ".join(missing[:10])
        suffix = f" (and {len(missing) - 10} more)" if len(missing) > 10 else ""
        result.add(
            WARNING,
            f"{len(missing)} column(s) in the published {dataset} {form_year} "
            f"layout are absent from this file: {preview}{suffix}.",
            str(path),
        )

    unexpected = layout.unexpected_in(header)
    if unexpected:
        preview = ", ".join(unexpected[:10])
        suffix = f" (and {len(unexpected) - 10} more)" if len(unexpected) > 10 else ""
        result.add(
            WARNING,
            f"{len(unexpected)} column(s) are not in the published "
            f"{dataset} {form_year} layout: {preview}{suffix}.",
            str(path),
        )

    if not missing and not unexpected:
        result.add(
            INFO,
            f"Matches the published {dataset} {form_year} layout exactly "
            f"({len(layout.fields)} fields).",
            str(path),
        )

    return result


def validate_dataset(
    directory: Path,
    dataset: str | None = None,
    form_year: int | None = None,
) -> ValidationResult:
    """Validate every CSV file under a directory."""

    result = ValidationResult()

    if not directory.exists():
        result.add(ERROR, f"Directory does not exist: {directory}")
        return result

    csv_files = find_csv_files(directory)
    if not csv_files:
        result.add(ERROR, "No CSV files were found.", str(directory))
        return result

    for path in csv_files:
        result.merge(validate_csv_file(path, dataset, form_year))

    return result
