"""
Command-line interface.

    401k-finder sync --year 2023
    401k-finder search "acme manufacturing"
    401k-finder plan 12-3456789/001 --evidence
    401k-finder providers --role RECORDKEEPER

The CLI is a first-class entry point, not a debugging aid: everything the
desktop application does is available here, which is what makes the tool usable
on a server, in a scheduled job, or over SSH.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from app.core.config import Settings, get_app_data_dir, get_database_path
from app.core.constants import LATEST_FORM_YEAR, ProviderRole
from app.core.exceptions import FinderError, ImportCancelled
from app.core.logging import configure_logging
from app.database.init_db import database_exists, initialize_database, reset_database
from app.database.schema import rebuild_fts
from app.database.session import read_session, session_scope
from app.dol.catalog import (
    CORE_DATASET_NAMES,
    DATASETS,
    Release,
    dataset_names_for_year,
    supported_years,
)
from app.dol.importer import import_directory
from app.evidence.trail import build_plan_evidence
from app.search.engine import SearchEngine
from app.search.query import PlanQuery, ProviderQuery, QueryOptions, SortOrder
from app.services import export as export_service
from app.services.stats import database_summary


def _money(value: float | None) -> str:
    if value is None:
        return "-"
    if abs(value) >= 1_000_000_000:
        return f"${value / 1_000_000_000:.2f}B"
    if abs(value) >= 1_000_000:
        return f"${value / 1_000_000:.1f}M"
    return f"${value:,.0f}"


def _print_progress(stage: str, dataset: str, done: int, total: int, message: str) -> None:
    if total:
        percent = min(100, int(done * 100 / total))
        sys.stderr.write(f"\r  [{stage:9}] {message[:60]:60} {percent:3d}%")
    else:
        sys.stderr.write(f"\r  [{stage:9}] {message[:66]:66}")
    sys.stderr.flush()

    if stage == "finalize" and done == total:
        sys.stderr.write("\n")


# ----------------------------------------------------------------------
# Commands
# ----------------------------------------------------------------------


def cmd_init(args: argparse.Namespace) -> int:
    version = initialize_database()
    print(f"Database ready at {get_database_path()} (schema version {version}).")
    print(f"Application data directory: {get_app_data_dir()}")
    return 0


def cmd_sync(args: argparse.Namespace) -> int:
    from app.services.sync import SyncService

    initialize_database()
    settings = Settings.load()

    years = args.year or settings.form_years or [LATEST_FORM_YEAR]
    release = Release(args.release) if args.release else Release(settings.release)

    exit_code = 0

    for year in years:
        print(f"\nSyncing form year {year} ({release.value})")

        with session_scope() as session:
            service = SyncService(
                session,
                settings=settings,
                progress=None if args.quiet else _print_progress,
            )

            try:
                report = service.sync_year(
                    year,
                    release=release,
                    datasets=tuple(args.dataset) if args.dataset else None,
                    core_only=not args.all_datasets,
                    force=args.force,
                )
            except ImportCancelled:
                print("\nCancelled.")
                return 130
            except FinderError as exc:
                print(f"\nFailed: {exc}", file=sys.stderr)
                exit_code = 1
                continue

        print(f"\n{report.summary()}")

        for outcome in report.failed:
            print(f"  FAILED {outcome.dataset}: {outcome.message}", file=sys.stderr)
            exit_code = 1

    return exit_code


def cmd_import(args: argparse.Namespace) -> int:
    initialize_database()
    settings = Settings.load()

    directory = args.path.resolve()
    print(f"Importing DOL files from {directory}")

    with session_scope() as session:
        stats = import_directory(
            session,
            directory,
            form_year=args.year,
            datasets=args.dataset or None,
            batch_size=settings.import_batch_size,
            progress=None if args.quiet else (
                lambda done, total, message: _print_progress("import", "", done, total, message)
            ),
        )

    print(f"\n{stats.summary()}")

    if stats.unmatched_ack_ids:
        print(
            f"  Note: {stats.unmatched_ack_ids:,} schedule rows referenced filings "
            f"not in the database. Import the matching F_5500 / F_5500_SF file for "
            f"the same year and re-run to attach them."
        )

    for error in stats.errors[:10]:
        print(f"  {error}", file=sys.stderr)

    from app.database.engine import get_engine

    rebuild_fts(get_engine())
    return 1 if stats.errors else 0


def cmd_search(args: argparse.Namespace) -> int:
    filters = {
        "state": args.state,
        "form_years": tuple(args.year) if args.year else (),
        "features": tuple(args.feature) if args.feature else (),
        "roles": tuple(args.role) if args.role else (),
        "provider_name": args.provider,
        "min_participants": args.min_participants,
        "min_assets": args.min_assets,
        "retirement_only": not args.include_welfare,
        "sort": SortOrder(args.sort),
        "limit": args.limit,
    }

    query = PlanQuery.parse(" ".join(args.text), **filters)

    with read_session() as session:
        engine = SearchEngine(session)
        total, capped = engine.count_plans_detailed(query)
        results = engine.search_plans(query, QueryOptions(include_parties=True, max_parties=40))

        if not results:
            print("No plans matched.")
            print("Run '401k-finder status' to check which years have been imported.")
            return 1

        # "+" marks a floor: a broad text search stops counting at the cap.
        print(f"{total:,}{'+' if capped else ''} plan(s) matched; showing {len(results)}.\n")

        for result in results:
            print(f"{result.plan_name}")
            print(
                f"  Sponsor: {result.sponsor_name or '-'}  |  "
                f"EIN {result.plan_key}  |  "
                f"{result.city or '-'}, {result.state or '-'}"
            )
            print(
                f"  {result.plan_category or 'UNKNOWN'}"
                f"{' [' + ', '.join(result.features) + ']' if result.features else ''}"
                f"  |  {result.participants or '-'} participants"
                f"  |  {_money(result.total_assets)}"
                f"  |  years {result.first_year}-{result.last_year}"
            )

            for party in result.primary_providers()[: args.providers]:
                codes = f" ({', '.join(party.service_codes)})" if party.service_codes else ""
                print(
                    f"    {party.role.replace('_', ' ').title():26} "
                    f"{party.display_name[:44]:44} "
                    f"[{party.schedule_code or '-'} {party.form_year}]{codes}"
                )

            print()

        if args.csv:
            path = export_service.export_plans_csv(results, args.csv)
            print(f"Wrote {path}")
        if args.json:
            path = export_service.export_plans_json(results, args.json)
            print(f"Wrote {path}")

    return 0


def cmd_plan(args: argparse.Namespace) -> int:
    query = PlanQuery.parse(args.identifier, retirement_only=False, limit=5)

    with read_session() as session:
        engine = SearchEngine(session)
        results = engine.search_plans(query, QueryOptions(include_parties=False))

        if not results:
            print(f"No plan matched '{args.identifier}'.")
            return 1

        if len(results) > 1 and not args.first:
            print(f"{len(results)} plans matched. Narrow the identifier, or use --first:\n")
            for result in results:
                print(f"  {result.plan_key}  {result.plan_name}  ({result.sponsor_name})")
            return 1

        plan_id = results[0].plan_id
        package = build_plan_evidence(session, plan_id)

        if package is None:
            print("Plan not found.")
            return 1

        print(package.explain())

        if args.filings:
            print("\nFilings on record:")
            for filing in package.filings:
                print(
                    f"  {filing.form_year}  {filing.form_type:8}  "
                    f"ACK_ID {filing.ack_id}  "
                    f"participants={filing.total_participants or '-'}  "
                    f"assets={_money(filing.total_assets_eoy)}"
                )

        if args.evidence:
            path = export_service.export_evidence_report(package, args.output)
            print(f"\nWrote evidence report to {path}")

    return 0


def cmd_providers(args: argparse.Namespace) -> int:
    query = ProviderQuery(
        text=" ".join(args.text) if args.text else "",
        role=args.role,
        state=args.state,
        min_plans=args.min_plans,
        sort=args.sort,
        limit=args.limit,
    )

    with read_session() as session:
        engine = SearchEngine(session)
        results = engine.search_providers(query)

        if not results:
            print("No providers matched.")
            return 1

        print(f"{'Provider':46} {'Role':22} {'Plans':>8} {'Participants':>14} {'Assets':>12}")
        print("-" * 106)

        for result in results:
            print(
                f"{result.display_name[:45]:46} "
                f"{(result.primary_role or '-')[:21]:22} "
                f"{result.plan_count:>8,} "
                f"{result.participant_count:>14,} "
                f"{_money(result.assets_under_administration):>12}"
            )

        if args.csv:
            path = export_service.export_providers_csv(results, args.csv)
            print(f"\nWrote {path}")

    return 0


def cmd_license(args: argparse.Namespace) -> int:
    from app.licensing import get_gate, machine_fingerprint, machine_label

    gate = get_gate()

    if args.license_action == "activate":
        result = gate.activate(args.key)
        print(result.message)
        if result.activation_limit is not None:
            print(
                f"  Machines used: {result.activation_count or '?'} "
                f"of {result.activation_limit}"
            )
        return 0 if result.ok else 1

    if args.license_action == "deactivate":
        if not args.yes:
            print("This releases the licence from this computer so it can be used elsewhere.")
            if input("Type 'release' to confirm: ").strip().lower() != "release":
                print("Cancelled.")
                return 1

        result = gate.deactivate()
        print(result.message)
        return 0 if result.ok else 1

    # Default: report the current position.
    status = gate.status(force_check=args.check)

    print(status.headline())

    if status.message and status.message != status.headline():
        print(f"  {status.message}")

    if status.key_suffix:
        print(f"  Key:            ...{status.key_suffix}")
    if status.customer_email:
        print(f"  Licensed to:    {status.customer_email}")
    if status.activation_limit is not None:
        print(
            f"  Machines used:  {status.activation_count if status.activation_count is not None else '?'}"
            f" of {status.activation_limit}"
        )
    if status.last_validated:
        print(f"  Last confirmed: {status.last_validated:%Y-%m-%d %H:%M} UTC")

    print(f"  Machine ID:     {machine_fingerprint()}")
    print(f"  Machine:        {machine_label()}")

    if not gate.config.enforced:
        print("\n  This build has no licence server configured, so no key is required.")

    return 0 if status.allows_use else 1


def cmd_status(args: argparse.Namespace) -> int:
    from app.services.sync import SyncService
    from app.ui import resources

    if args.branding:
        # Confirms which branding assets a build actually resolved. In a
        # packaged application this reports the unpacked bundle directory, so it
        # is the quickest way to tell whether an icon made it into the build.
        found = resources.describe()
        print(f"Resource folder: {found['resource_dir']}")
        for slot in ("icon", "logo", "stylesheet"):
            print(f"  {slot + ':':12} {found[slot] or 'not set (using Qt default)'}")
        print()

    # On a machine where the application has never been opened there is no
    # database yet, and every count below would fail on a missing table. This
    # is the first command a new installation runs — reporting "nothing yet" is
    # the answer, not a traceback.
    if not database_exists():
        print(f"Database: {get_database_path()}")
        print("  Not created yet. Run 'init', or open the application once.")
        return 0

    with read_session() as session:
        summary = database_summary(session)

        print(f"Database: {get_database_path()}")
        print(f"  Plans:            {summary.plans:,} ({summary.retirement_plans:,} retirement)")
        print(f"  Filings:          {summary.filings:,}")
        print(f"  Providers:        {summary.providers:,}")
        print(f"  Engagements:      {summary.parties:,}")
        print(f"  Schedule rows:    {summary.schedule_records:,}")
        print(f"  Evidence records: {summary.evidence:,}")

        if summary.years:
            print(f"  Form years:       {', '.join(str(year) for year in summary.years)}")

        if summary.by_category:
            print("\nPlans by category:")
            for category, count in summary.by_category:
                print(f"  {category:26} {count:>9,}")

        if summary.by_feature:
            print("\nRetirement account types:")
            for feature, count in summary.by_feature:
                print(f"  {feature:26} {count:>9,}")

        if summary.by_role:
            print("\nProvider engagements by role:")
            for role, count in summary.by_role:
                print(f"  {role:26} {count:>9,}")

        service = SyncService(session)
        records = service.status(args.year)

        if records:
            print("\nImported datasets:")
            for record in records:
                print(
                    f"  {record.form_year}  {record.dataset:22} {record.release:8} "
                    f"{record.status:12} {record.rows_imported:>10,} rows"
                    + (f"  {record.error[:40]}" if record.error else "")
                )
        else:
            print("\nNo datasets imported yet. Run '401k-finder sync --year 2023'.")

    return 0


def cmd_datasets(args: argparse.Namespace) -> int:
    year = args.year or LATEST_FORM_YEAR
    published = set(dataset_names_for_year(year))

    print(f"DOL datasets published for form year {year}:\n")
    print(f"{'Dataset':26} {'Kind':18} {'Core':6} Description")
    print("-" * 100)

    for spec in DATASETS:
        if spec.name not in published:
            continue
        core = "yes" if spec.name in CORE_DATASET_NAMES else ""
        print(f"{spec.name:26} {spec.kind.value:18} {core:6} {spec.title}")

    print(f"\nYears available offline: {', '.join(str(y) for y in supported_years())}")
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    from app.dol.validator import validate_dataset

    result = validate_dataset(args.path.resolve(), args.dataset, args.year)

    print(result.summary())
    for issue in result.issues:
        if issue.severity != "INFO" or args.verbose:
            print(f"  {issue}")

    return 0 if result.valid else 1


def cmd_reset(args: argparse.Namespace) -> int:
    if not args.yes:
        print(f"This deletes {get_database_path()} and everything imported into it.")
        print("The DOL source files are untouched and can be re-imported.")
        answer = input("Type 'delete' to confirm: ").strip().lower()
        if answer != "delete":
            print("Cancelled.")
            return 1

    reset_database()
    print("Database rebuilt empty.")
    return 0


# ----------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="401k-finder",
        description=(
            "Search U.S. Department of Labor Form 5500 filings to find "
            "retirement plans and the firms that hold and administer them."
        ),
    )
    parser.add_argument("--verbose", action="store_true", help="Log debug detail.")

    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init", help="Create the local database.").set_defaults(func=cmd_init)

    sync = sub.add_parser("sync", help="Download and import DOL datasets.")
    sync.add_argument("--year", type=int, action="append", help="Form year (repeatable).")
    sync.add_argument("--release", choices=["Latest", "All"], help="DOL release to fetch.")
    sync.add_argument("--dataset", action="append", help="Specific dataset (repeatable).")
    sync.add_argument("--all-datasets", action="store_true", help="Fetch every dataset, not just the core set.")
    sync.add_argument("--force", action="store_true", help="Re-download and re-import completed datasets.")
    sync.add_argument("--quiet", action="store_true", help="Suppress progress output.")
    sync.set_defaults(func=cmd_sync)

    imp = sub.add_parser("import", help="Import DOL CSV files already on disk.")
    imp.add_argument("path", type=Path, help="Directory containing DOL CSV files.")
    imp.add_argument("--year", type=int, help="Only import this form year.")
    imp.add_argument("--dataset", action="append", help="Only import these datasets.")
    imp.add_argument("--quiet", action="store_true")
    imp.set_defaults(func=cmd_import)

    search = sub.add_parser("search", help="Search plans.")
    search.add_argument("text", nargs="*", help="Sponsor, plan name, or EIN.")
    search.add_argument("--state", help="Two-letter state code.")
    search.add_argument("--year", type=int, action="append", help="Form year filter (repeatable).")
    search.add_argument("--feature", action="append", help="Plan feature, e.g. 401K, 403B, ESOP.")
    search.add_argument("--role", action="append", help="Only plans with a provider in this role.")
    search.add_argument("--provider", help="Only plans served by this provider.")
    search.add_argument("--min-participants", type=int)
    search.add_argument("--min-assets", type=float)
    search.add_argument("--include-welfare", action="store_true", help="Include non-retirement plans.")
    search.add_argument("--sort", choices=[item.value for item in SortOrder], default="relevance")
    search.add_argument("--limit", type=int, default=25)
    search.add_argument("--providers", type=int, default=6, help="Providers to show per plan.")
    search.add_argument("--csv", type=Path, help="Also write results to this CSV file.")
    search.add_argument("--json", type=Path, help="Also write results to this JSON file.")
    search.set_defaults(func=cmd_search)

    plan = sub.add_parser("plan", help="Show one plan and the evidence behind it.")
    plan.add_argument("identifier", help="EIN, EIN/plan-number, or plan name.")
    plan.add_argument("--first", action="store_true", help="Use the first match if several.")
    plan.add_argument("--filings", action="store_true", help="List every filing on record.")
    plan.add_argument("--evidence", action="store_true", help="Write a full evidence report.")
    plan.add_argument("--output", type=Path, help="Where to write the evidence report.")
    plan.set_defaults(func=cmd_plan)

    providers = sub.add_parser("providers", help="Search providers.")
    providers.add_argument("text", nargs="*")
    providers.add_argument("--role", choices=[role.value for role in ProviderRole])
    providers.add_argument("--state")
    providers.add_argument("--min-plans", type=int)
    providers.add_argument("--sort", choices=["plans", "name", "assets", "participants"], default="plans")
    providers.add_argument("--limit", type=int, default=30)
    providers.add_argument("--csv", type=Path)
    providers.set_defaults(func=cmd_providers)

    status = sub.add_parser("status", help="Show what has been imported.")
    status.add_argument("--year", type=int)
    status.add_argument(
        "--branding",
        action="store_true",
        help="Also report which icon, logo and style sheet this build resolved.",
    )
    status.set_defaults(func=cmd_status)

    datasets = sub.add_parser("datasets", help="List the DOL datasets for a form year.")
    datasets.add_argument("--year", type=int)
    datasets.set_defaults(func=cmd_datasets)

    validate = sub.add_parser("validate", help="Check DOL files against their published layouts.")
    validate.add_argument("path", type=Path)
    validate.add_argument("--dataset")
    validate.add_argument("--year", type=int)
    validate.add_argument("--verbose", action="store_true")
    validate.set_defaults(func=cmd_validate)

    license_parser = sub.add_parser("license", help="Activate or inspect the licence.")
    license_sub = license_parser.add_subparsers(dest="license_action")
    license_parser.set_defaults(func=cmd_license, license_action="status", key=None, check=False, yes=False)

    license_status = license_sub.add_parser("status", help="Show the current licence.")
    license_status.add_argument(
        "--check", action="store_true", help="Re-confirm with the licence server now."
    )
    license_status.set_defaults(func=cmd_license, key=None, yes=False)

    license_activate = license_sub.add_parser("activate", help="Activate a licence key.")
    license_activate.add_argument("key", help="The key from your purchase email.")
    license_activate.set_defaults(func=cmd_license, check=False, yes=False)

    license_deactivate = license_sub.add_parser(
        "deactivate", help="Release the licence from this computer."
    )
    license_deactivate.add_argument("--yes", action="store_true", help="Skip the confirmation.")
    license_deactivate.set_defaults(func=cmd_license, key=None, check=False)

    reset = sub.add_parser("reset", help="Delete and rebuild the local database.")
    reset.add_argument("--yes", action="store_true", help="Skip the confirmation prompt.")
    reset.set_defaults(func=cmd_reset)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    import logging

    configure_logging(level=logging.DEBUG if args.verbose else logging.WARNING)

    try:
        return int(args.func(args))
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130
    except FinderError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
