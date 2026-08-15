#!/usr/bin/env python3
"""
Refresh the vendored DOL record layouts.

Fetches every ``*_layout.txt`` published on the EBSA Form 5500 dataset page and
rewrites ``app/dol/layouts/data/<year>.json``. Run this when DOL publishes a new
form year, or revises an existing layout.

    python -m scripts.refresh_layouts                  # every year
    python -m scripts.refresh_layouts --year 2025      # one year
    python -m scripts.refresh_layouts --check          # report drift, write nothing

``--check`` is the one to run in CI: it fails if what DOL publishes no longer
matches what is vendored, which is how a silent layout change gets noticed
before it corrupts an import.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import contextlib
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.core.constants import DOL_FILE_BASE_URL  # noqa: E402
from app.core.exceptions import DownloadError  # noqa: E402
from app.dol.catalog import DATASETS  # noqa: E402
from app.dol.downloader import DOLDownloader  # noqa: E402

OUTPUT_DIR = REPO_ROOT / "app" / "dol" / "layouts" / "data"

DEFAULT_YEARS = tuple(range(2009, 2027))


def layout_url(form_year: int, dataset: str) -> str:
    return (
        f"{DOL_FILE_BASE_URL}/{form_year}/Latest/"
        f"{dataset}_{form_year}_Latest_layout.txt"
    )


def parse_layout(text: str) -> list[dict[str, object]]:
    """
    Parse a DOL layout file.

        FIELD_POSITION,FIELD_NAME,TYPE,SIZE (only for text fields)
        ===========================================
        1,ACK_ID,TEXT,30
    """

    fields: list[dict[str, object]] = []

    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("=") or line.startswith("FIELD_POSITION"):
            continue

        parts = [part.strip() for part in line.split(",")]
        if len(parts) < 3 or not parts[0].isdigit():
            continue

        entry: dict[str, object] = {
            "p": int(parts[0]),
            "n": parts[1],
            "t": parts[2],
        }

        if len(parts) > 3 and parts[3] not in ("", "0"):
            # A non-numeric size means DOL changed the layout format; keep the
            # field, just without a declared size.
            with contextlib.suppress(ValueError):
                entry["s"] = int(parts[3])

        fields.append(entry)

    fields.sort(key=lambda field: field["p"])  # type: ignore[arg-type,return-value]
    return fields


def fetch_year(
    form_year: int,
    downloader: DOLDownloader,
    workers: int = 8,
) -> dict[str, list[dict[str, object]]]:
    """Fetch every dataset layout published for a form year."""

    def fetch(dataset: str) -> tuple[str, list[dict[str, object]]]:
        try:
            text = downloader.fetch_text(layout_url(form_year, dataset))
        except DownloadError:
            return dataset, []

        if "FIELD_POSITION" not in text:
            return dataset, []

        return dataset, parse_layout(text)

    found: dict[str, list[dict[str, object]]] = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        for dataset, fields in pool.map(fetch, [spec.name for spec in DATASETS]):
            if fields:
                found[dataset] = fields

    return found


def write_year(form_year: int, datasets: dict[str, list[dict[str, object]]]) -> Path:
    """Write one year's layouts, one dataset per line so diffs stay readable."""

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    target = OUTPUT_DIR / f"{form_year}.json"

    separators = (",", ":")
    lines = [
        "{",
        f' "form_year": {form_year},',
        f' "source": "{DOL_FILE_BASE_URL}/{form_year}/Latest/",',
        ' "datasets": {',
    ]

    items = sorted(datasets.items())
    for index, (name, fields) in enumerate(items):
        comma = "" if index == len(items) - 1 else ","
        lines.append(f"  {json.dumps(name)}: {json.dumps(fields, separators=separators)}{comma}")

    lines += [" }", "}", ""]

    target.write_text("\n".join(lines), encoding="utf-8")
    return target


def load_vendored(form_year: int) -> dict[str, list[dict[str, object]]]:
    path = OUTPUT_DIR / f"{form_year}.json"

    if not path.exists():
        return {}

    return json.loads(path.read_text(encoding="utf-8"))["datasets"]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--year", type=int, action="append", help="Form year (repeatable).")
    parser.add_argument("--check", action="store_true", help="Report drift without writing.")
    parser.add_argument("--timeout", type=float, default=90.0)
    args = parser.parse_args()

    years = args.year or list(DEFAULT_YEARS)
    downloader = DOLDownloader(timeout=args.timeout)

    drift = 0

    for form_year in years:
        print(f"{form_year}: fetching…", flush=True)

        try:
            published = fetch_year(form_year, downloader)
        except Exception as exc:  # noqa: BLE001
            print(f"  error: {exc}", file=sys.stderr)
            drift += 1
            continue

        if not published:
            print("  no layouts published (yet)")
            continue

        vendored = load_vendored(form_year)

        added = sorted(set(published) - set(vendored))
        removed = sorted(set(vendored) - set(published))
        changed = sorted(
            dataset
            for dataset in set(published) & set(vendored)
            if published[dataset] != vendored[dataset]
        )

        if args.check:
            if added or removed or changed:
                drift += 1
                print(f"  DRIFT: added={added} removed={removed} changed={changed}")
            else:
                print(f"  up to date ({len(published)} datasets)")
        else:
            path = write_year(form_year, published)
            summary = (
                f"added={len(added)} removed={len(removed)} changed={len(changed)}"
                if vendored
                else "new"
            )
            print(f"  wrote {path.name}: {len(published)} datasets ({summary})")

    if args.check and drift:
        print(
            f"\n{drift} year(s) differ from what DOL publishes. "
            f"Run without --check to update, then re-run the test suite.",
            file=sys.stderr,
        )
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
