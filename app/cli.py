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
import contextlib
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


def cmd_index(args: argparse.Namespace) -> int:
    """Fetch the employer index for many years at once."""

    from app.services.coverage import coverage, summarise
    from app.services.sync import SyncService

    initialize_database()
    settings = Settings.load()

    years = args.year or list(supported_years())

    print(
        f"Indexing {len(years)} form year(s): {years[0]}–{years[-1]}.\n"
        f"This fetches the two filing forms only — enough to match an employer "
        f"to a plan.\nProvider detail needs a full sync of the years that matter; "
        f"'401k-finder sync --year N'\ndoes that once you know which they are.\n"
    )

    with session_scope() as session:
        service = SyncService(
            session,
            settings=settings,
            progress=None if args.quiet else _print_progress,
        )

        try:
            reports = service.sync_index(years, force=args.force)
        except ImportCancelled:
            print("\nCancelled.")
            return 130
        except FinderError as exc:
            print(f"\nFailed: {exc}", file=sys.stderr)
            return 1

    failures = sum(len(report.failed) for report in reports)

    with read_session() as session:
        print(f"\n{summarise(coverage(session))}")

    if failures:
        print(f"  {failures} dataset(s) failed; re-run to retry them.", file=sys.stderr)

    return 1 if failures else 0


def cmd_changes(args: argparse.Namespace) -> int:
    """Report plans that changed provider between filed years."""

    from app.providers.changes import ChangeDetector, ChangeQuery

    if not database_exists():
        print(f"No database yet at {get_database_path()}.", file=sys.stderr)
        return 1

    query = ChangeQuery(
        role=args.role,
        year=args.year,
        from_provider=args.from_provider,
        to_provider=args.to_provider,
        state=args.state,
        min_participants=args.min_participants,
        min_assets=args.min_assets,
        include_gained=args.include_appointments,
        include_lost=args.include_departures,
        limit=args.limit,
    )

    with read_session() as session:
        report = ChangeDetector(session).find(query)

    if not report.years_compared:
        print(
            "Nothing to compare. Provider changes need at least two form years "
            "imported\nwith the schedules that name providers — see "
            "'401k-finder status'.",
            file=sys.stderr,
        )
        return 1

    span = f"{report.years_compared[0]}–{report.years_compared[-1]}"
    print(f"{report.total:,} {args.role.lower().replace('_', ' ')} change(s) across {span}.\n")

    if not report.total:
        return 1

    for change in report.changes:
        print(change.describe())
        print(
            f"  EIN {change.plan_key}  |  {change.state or '-'}  |  "
            f"{format(change.participants, ',') if change.participants else '-'} participants"
            f"  |  {_money(change.total_assets)}"
        )
        print(
            f"  source: schedule {change.schedule_code or '?'}, "
            f"field {change.source_field or '?'}"
        )
        print()

    flows = report.flows()
    if flows and not args.no_summary:
        print("Where plans moved:")
        for source, target, count, assets in flows[:20]:
            print(f"  {source} -> {target}: {count} plan(s), {_money(assets)}")
        print()

    if args.csv:
        path = export_service.export_provider_changes_csv(report.changes, args.csv)
        print(f"Wrote {path}")

    return 0


def cmd_trace(args: argparse.Namespace) -> int:
    """Trace a work history against the filings, for a lost-account search."""

    from app.trace import AccountTracer, WorkHistory, looks_like_ssn
    from app.trace.packet import render_report

    # Checked on the raw arguments, before anything is constructed. Employment
    # redacts on the way in, so by the time a history exists the number is gone
    # -- which is right for the log and the database, but would leave the person
    # staring at an empty report with no idea why.
    raw = " ".join(filter(None, [*(args.employer or []), args.name or ""]))
    if args.history and args.history.is_file():
        with contextlib.suppress(OSError):
            raw += " " + args.history.read_text(encoding="utf-8-sig", errors="replace")

    if looks_like_ssn(raw):
        print(
            "That looks like a Social Security number. It has not been searched for, "
            "logged or saved.\n\n"
            "Form 5500 is what employers file about their plans: it names plans, not "
            "people.\nAcross all 448 published record layouts there is no participant "
            "name, no Social\nSecurity number and no individual balance, so an SSN has "
            "nothing to match against\nhere.\n\n"
            "Search by employer instead:\n"
            "  401k-finder trace --employer 'Acme Manufacturing' --state OH --from 2008 "
            "--to 2012\n\n"
            "The report ends with the registries that *can* be searched by Social "
            "Security\nnumber, including the Department of Labor's Retirement Savings "
            "Lost and Found.",
            file=sys.stderr,
        )
        return 2

    if args.history:
        try:
            history = WorkHistory.from_csv(args.history, person=args.name or "")
        except (OSError, ValueError) as exc:
            print(f"Could not read {args.history}: {exc}", file=sys.stderr)
            return 1
    else:
        if not args.employer:
            print(
                "Give at least one --employer, or a --history CSV.\n"
                "  401k-finder trace --employer 'Acme Manufacturing' --state OH "
                "--from 2008 --to 2012",
                file=sys.stderr,
            )
            return 2

        history = WorkHistory(person=args.name or "")
        for employer in args.employer:
            history.add(
                employer,
                state=args.state,
                city=args.city,
                start_year=args.from_year,
                end_year=args.to_year,
            )

    if not database_exists():
        print(
            f"No database yet at {get_database_path()}.\n"
            f"Run '401k-finder sync --year 2023' to download a form year first.",
            file=sys.stderr,
        )
        return 1

    with read_session() as session:
        report = AccountTracer(session).trace(history, limit_per_job=args.limit)

    text = render_report(report, letters=args.letters)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"Wrote {args.output}")
        print(
            f"  {report.total_matches} plan(s) across "
            f"{len(report.jobs_with_matches)} of {len(history)} job(s)."
        )
    else:
        print(text)

    return 0 if report.total_matches else 1


def cmd_license(args: argparse.Namespace) -> int:
    from app.licensing import get_gate, machine_fingerprint, machine_label

    gate = get_gate()

    if args.license_action == "activate":
        result = gate.activate(args.key)
        print(result.message)

        if result.ok and result.expires is not None:
            print(f"  Valid until:  {result.expires:%d %B %Y}")

        return 0 if result.ok else 1

    if args.license_action == "deactivate":
        if not args.yes:
            print("This removes the licence key from this computer.")
            if input("Type 'remove' to confirm: ").strip().lower() != "remove":
                print("Cancelled.")
                return 1

        result = gate.deactivate()
        print(result.message)
        return 0 if result.ok else 1

    # Default: report the current position.
    status = gate.status()

    print(status.headline())

    if status.message and status.message != status.headline():
        print(f"  {status.message}")

    if status.label:
        print(f"  Licensed to:  {status.label}")
    if status.expires is not None:
        remaining = status.days_remaining
        suffix = f" ({remaining} days)" if remaining is not None and remaining >= 0 else ""
        print(f"  Valid until:  {status.expires:%d %B %Y}{suffix}")
    if status.activated_at:
        print(f"  Activated:    {status.activated_at:%Y-%m-%d %H:%M} UTC")

    # The Machine ID is what a customer sends to buy or move a licence, so it
    # is printed whether or not anything is activated.
    print(f"  Machine ID:   {machine_fingerprint()}")
    print(f"  Machine:      {machine_label()}")

    if not gate.config.enforced:
        print("\n  This build has no licence key configured, so none is required.")
    elif not status.allows_use:
        print(f"\n  To get a licence, email {gate.config.support_email}")
        print("  with the Machine ID above.")

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

        from app.plans.successor import transfer_counts
        from app.services.coverage import coverage, summarise

        transfers, resolved = transfer_counts(session)
        if transfers:
            print(f"  Asset transfers:  {transfers:,} ({resolved:,} resolved to a plan held here)")

        entries = coverage(session)
        if entries:
            print(f"\nCoverage: {summarise(entries)}")
            for entry in entries:
                print(f"  {entry.form_year}  {entry.depth.label}")

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

    index = sub.add_parser(
        "index",
        help="Fetch the employer index for every form year (small and fast).",
        description=(
            "Downloads the two filing forms for each year -- enough to match an "
            "employer to a plan, at a fraction of the size of a full sync. Use "
            "this to make a whole working life searchable, then sync in full "
            "only the years that matched."
        ),
    )
    index.add_argument("--year", type=int, action="append", help="Limit to these years.")
    index.add_argument("--force", action="store_true", help="Re-fetch years already held.")
    index.add_argument("--quiet", action="store_true")
    index.set_defaults(func=cmd_index)

    changes = sub.add_parser(
        "changes",
        help="Plans that changed provider between years.",
        description=(
            "Compares each plan's filed provider from one year to the next. "
            "Needs at least two form years imported with the provider schedules."
        ),
    )
    changes.add_argument(
        "--role",
        default=ProviderRole.RECORDKEEPER.value,
        choices=[role.value for role in ProviderRole],
    )
    changes.add_argument("--year", type=int, help="Only changes landing in this year.")
    changes.add_argument("--from-provider", help="Plans that moved away from this firm.")
    changes.add_argument("--to-provider", help="Plans that moved to this firm.")
    changes.add_argument("--state")
    changes.add_argument("--min-participants", type=int)
    changes.add_argument("--min-assets", type=float)
    changes.add_argument(
        "--include-appointments",
        action="store_true",
        help="Also report a role appearing for the first time.",
    )
    changes.add_argument(
        "--include-departures",
        action="store_true",
        help="Also report a role no longer filed. Often an unimported schedule.",
    )
    changes.add_argument("--no-summary", action="store_true", help="Skip the flow table.")
    changes.add_argument("--limit", type=int, default=500)
    changes.add_argument("--csv", type=Path)
    changes.set_defaults(func=cmd_changes)

    trace = sub.add_parser(
        "trace",
        help="Find retirement plans from a work history (for a lost-account search).",
        description=(
            "Matches employers you have worked for against the filed plans, and "
            "reports who was holding the money. Form 5500 holds no participant "
            "records, so this identifies the plan and who to ask -- it cannot "
            "confirm an account exists in your name."
        ),
    )
    trace.add_argument(
        "--employer",
        action="append",
        help="An employer to search for. Repeat for several.",
    )
    trace.add_argument(
        "--history",
        type=Path,
        help=(
            "CSV of employers. Columns: employer (required), city, state, "
            "start_year, end_year, note."
        ),
    )
    trace.add_argument("--name", help="The person's name, for the report heading.")
    trace.add_argument("--state", help="Two-letter state, applied to every --employer.")
    trace.add_argument("--city")
    trace.add_argument("--from", dest="from_year", type=int, help="First year worked.")
    trace.add_argument("--to", dest="to_year", type=int, help="Last year worked.")
    trace.add_argument("--limit", type=int, default=8, help="Plans per employer.")
    trace.add_argument(
        "--letters", action="store_true", help="Append a claim letter per employer."
    )
    trace.add_argument("--output", type=Path, help="Write the report to a file.")
    trace.set_defaults(func=cmd_trace)

    license_parser = sub.add_parser("license", help="Activate or inspect the licence.")
    license_sub = license_parser.add_subparsers(dest="license_action")
    license_parser.set_defaults(
        func=cmd_license, license_action="status", key=None, yes=False
    )

    license_status = license_sub.add_parser(
        "status", help="Show the current licence and this computer's Machine ID."
    )
    license_status.set_defaults(func=cmd_license, key=None, yes=False)

    license_activate = license_sub.add_parser("activate", help="Install a licence key.")
    license_activate.add_argument("key", help="The key from your licence email.")
    license_activate.set_defaults(func=cmd_license, yes=False)

    license_deactivate = license_sub.add_parser(
        "deactivate", help="Remove the licence key from this computer."
    )
    license_deactivate.add_argument("--yes", action="store_true", help="Skip the confirmation.")
    license_deactivate.set_defaults(func=cmd_license, key=None)

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
