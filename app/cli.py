import zipfile
import tempfile
from pathlib import Path

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, Confirm
from rich import box

from app.search import perform_search
from app.providers import add_full_provider
from app.models import (
    search_provider_directory,
    get_provider_identity_by_name,
    create_provider_identity,
    add_provider_alias,
    add_provider_name_history,
)
from app.datasets import (
    fetch_dataset_catalog,
    get_latest_year,
    calculate_package_sizes,
    download_and_process_package,
    check_disk_space,
    classify_file_type,
    process_extracted_files,
)
from app.exports import export_result
from app.health import run_health_check
from app.utils import human_readable_size, get_free_disk_space, clear_screen
from app.config import load_config

console = Console()


def show_banner():
    console.print(
        Panel.fit(
            "[bold cyan]401K PROVIDER FINDER[/]\n"
            "[dim]U.S. Retirement Plan Research Tool[/]",
            border_style="bright_blue",
            box=box.ROUNDED,
        )
    )


def main_menu():
    """Interactive main menu loop."""
    while True:
        clear_screen()          # <-- ADDED
        show_banner()
        console.print("1. Find 401(k) Provider")
        console.print("2. Search Company / EIN")
        console.print("3. Provider History")
        console.print("4. Provider Directory")
        console.print("5. Dataset Manager")
        console.print("6. Database Statistics")
        console.print("7. Configuration")
        console.print("8. Diagnostics / Health Check")
        console.print("9. Export Results")
        console.print("0. Exit")
        choice = Prompt.ask("Enter choice", choices=[str(i) for i in range(10)])
        if choice == "1":
            clear_screen()
            find_provider_flow()
        elif choice == "2":
            clear_screen()
            company_ein_flow()
        elif choice == "3":
            clear_screen()
            historical_flow()
        elif choice == "4":
            clear_screen()
            provider_directory_flow()
        elif choice == "5":
            clear_screen()
            dataset_manager_menu()
        elif choice == "6":
            clear_screen()
            db_stats()
        elif choice == "7":
            clear_screen()
            config_menu()
        elif choice == "8":
            clear_screen()
            run_health_check()
            Prompt.ask("Press Enter to return to main menu")
        elif choice == "9":
            clear_screen()
            export_menu()
        elif choice == "0":
            console.print("[bold]Goodbye![/]")
            break


def find_provider_flow():
    company = Prompt.ask("Enter company name")
    year = Prompt.ask("Enter plan year", default="2025")
    console.print("[1/6] Searching local company index...")
    console.print("[2/6] Matching EIN...")
    console.print("[3/6] Identifying retirement plans...")
    console.print("[4/6] Analyzing service providers...")
    console.print("[5/6] Classifying recordkeeper...")
    console.print("[6/6] Resolving provider identity...")
    try:
        year_int = int(year)
    except ValueError:
        console.print("[red]Invalid year[/]")
        Prompt.ask("Press Enter to continue")
        return
    result = perform_search(company, year_int)
    display_result(result)


def display_result(result):
    table = Table(show_header=False, box=box.SIMPLE)
    table.add_column("Field", style="bold cyan")
    table.add_column("Value")
    table.add_row("Company", result.get("company", ""))
    table.add_row("EIN", result.get("ein", ""))
    table.add_row("Plan", result.get("plan", ""))
    table.add_row(
        "Plan Year", str(result.get("fallback_year", result.get("year", "")))
    )
    table.add_row(
        "Provider (Filing)", result.get("recordkeeper_filing_name", "")
    )
    if "recordkeeper_identity" in result and result["recordkeeper_identity"]:
        table.add_row("Provider Identity", result["recordkeeper_identity"])
    if (
        "recordkeeper_current" in result
        and result["recordkeeper_current"] != result.get("recordkeeper_identity")
    ):
        table.add_row("Current Name", result["recordkeeper_current"])
    if "provider_login_url" in result:
        table.add_row("Provider Login", result["provider_login_url"])
    if "confidence" in result:
        conf = result["confidence"]
        if isinstance(conf, dict):
            overall = conf.get("overall", "N/A")
        else:
            overall = conf
        table.add_row("Confidence", f"{overall}%")
    console.print(Panel(table, title="Search Result", border_style="green"))
    if Confirm.ask("Export this result?", default=False):
        export_result(result)
    if Confirm.ask("Show evidence?", default=False):
        for ev in result.get("evidence", []):
            console.print(f"  - {ev}")
    Prompt.ask("Press Enter to continue")


def company_ein_flow():
    company = Prompt.ask("Enter company name")
    from app.ein import find_ein

    candidates = find_ein(company)
    if candidates:
        for c in candidates:
            console.print(f"EIN: {c['ein']} (confidence: {c['confidence']}%)")
    else:
        console.print("[red]No EIN found.[/]")
    Prompt.ask("Press Enter to continue")


def historical_flow():
    console.print(
        "[yellow]Provider history timeline will be displayed when implemented fully.[/]"
    )
    Prompt.ask("Press Enter to continue")


def provider_directory_flow():
    console.print("1. Search Provider")
    console.print("2. Add Provider Identity")
    console.print("3. Manage Aliases")
    choice = Prompt.ask("Choice", choices=["1", "2", "3"])
    if choice == "1":
        name = Prompt.ask("Provider name")
        results = search_provider_directory(name)
        if results:
            for r in results:
                console.print(
                    f"{r['legal_name']} | Login: {r['login_url']} | Phone: {r['phone']}"
                )
        else:
            console.print("[red]Not found[/]")
    elif choice == "2":
        canonical = Prompt.ask("Canonical name")
        display = Prompt.ask("Display name (optional)", default="")
        domain = Prompt.ask("Domain (optional)")
        login = Prompt.ask("Login URL (optional)")
        phone = Prompt.ask("Phone (optional)")
        add_full_provider(
            canonical, display or canonical, display, domain, login, phone
        )
        console.print("[green]Provider identity added.[/]")
    elif choice == "3":
        identity_name = Prompt.ask("Canonical identity name")
        identity = get_provider_identity_by_name(identity_name)
        if not identity:
            console.print("[red]Identity not found.[/]")
            return
        console.print(f"Managing aliases for {identity['canonical_name']}")
        alias = Prompt.ask("Alias name")
        alias_type = Prompt.ask(
            "Alias type",
            choices=[
                "FORM_5500_NAME",
                "HISTORICAL_NAME",
                "BRAND",
                "LEGAL_ENTITY",
                "OTHER",
            ],
            default="FORM_5500_NAME",
        )
        add_provider_alias(identity["id"], alias, alias_type)
        console.print("[green]Alias added.[/]")
    Prompt.ask("Press Enter to continue")


def dataset_manager_menu():
    console.print("1. Install/Update Dataset")
    console.print("2. Download Historical Dataset")
    console.print("3. Show Installed Datasets")
    console.print("4. Validate Datasets")
    console.print("5. Backup Database")
    choice = Prompt.ask("Choice", choices=["1", "2", "3", "4", "5"])
    if choice == "1":
        install_dataset_interactive()
    elif choice == "2":
        year_str = Prompt.ask("Year to download")
        try:
            year = int(year_str)
        except ValueError:
            console.print("[red]Invalid year[/]")
            Prompt.ask("Press Enter to continue")
            return
        package = Prompt.ask(
            "Package (essential/standard/full)",
            choices=["essential", "standard", "full"],
            default="essential",
        )
        try:
            download_and_process_package(year, package)
            console.print("[green]Dataset installed successfully.[/]")
        except Exception as e:
            console.print(f"[red]Error: {e}[/]")
    elif choice == "3":
        from app.database import get_connection

        conn = get_connection()
        years = conn.execute(
            "SELECT DISTINCT dataset_year FROM plans ORDER BY dataset_year"
        ).fetchall()
        if years:
            console.print(
                "Installed dataset years:",
                ", ".join(str(y["dataset_year"]) for y in years),
            )
        else:
            console.print("[yellow]No datasets installed.[/]")
    elif choice == "4":
        console.print("Validation not yet implemented.")
    elif choice == "5":
        console.print("Backup not yet implemented.")
    Prompt.ask("Press Enter to continue")


def install_dataset_interactive():
    catalog = fetch_dataset_catalog()
    if not catalog:
        console.print("[red]Could not fetch dataset catalog. Check network.[/]")
        Prompt.ask("Press Enter to continue")
        return
    latest = get_latest_year(catalog)
    console.print(f"Latest available DOL dataset year: {latest}")
    console.print("Select package:")
    console.print("1. Essential")
    console.print("2. Standard")
    console.print("3. Full")
    console.print("4. Custom")
    console.print("5. Offline / Skip")
    pkg_choice = Prompt.ask("Choice", choices=["1", "2", "3", "4", "5"])
    if pkg_choice == "5":
        return
    pkg_map = {"1": "essential", "2": "standard", "3": "full", "4": "custom"}
    package = pkg_map[pkg_choice]
    if package == "custom":
        files = catalog[latest]
        selected = []
        for fname, url, size in files:
            ftype = classify_file_type(fname, latest)
            size_str = human_readable_size(size) if size else "unknown"
            if Confirm.ask(f"Include {fname} ({size_str})?", default=False):
                selected.append((fname, url, size, ftype))
        if not selected:
            console.print("[yellow]No files selected.[/]")
            Prompt.ask("Press Enter to continue")
            return
        comp_total = sum(sz for _, _, sz, _ in selected if sz) or 0
        extract_total = int(comp_total * 8.0) if comp_total else 0
        sizes = {
            "compressed": comp_total,
            "extracted": extract_total,
            "database": int(extract_total * 0.8),
            "temp_needed": comp_total + extract_total,
            "file_list": selected,
        }
    else:
        sizes = calculate_package_sizes(catalog, latest, package)
    if not sizes:
        console.print("[red]No files available for selected package.[/]")
        Prompt.ask("Press Enter to continue")
        return
    console.print("Download size estimate:")
    console.print(
        f"  Compressed: {human_readable_size(sizes['compressed']) if sizes['compressed'] else 'unknown'}"
    )
    console.print(
        f"  Extracted: ~{human_readable_size(sizes['extracted']) if sizes['extracted'] else 'unknown'}"
    )
    console.print(
        f"  Database: ~{human_readable_size(sizes['database']) if sizes['database'] else 'unknown'}"
    )
    free = get_free_disk_space()
    if free:
        console.print(f"Available disk space: {human_readable_size(free)}")
    if not Confirm.ask("Proceed with download?", default=True):
        return
    try:
        if package == "custom":
            # Custom download: fetch each file individually.
            from app.downloader import download_file
            from app.validation import validate_zip_integrity

            config = load_config()
            raw_dir = Path(config["raw_dir"]) / str(latest)
            raw_dir.mkdir(parents=True, exist_ok=True)
            for fname, url, size, ftype in selected:
                dest = raw_dir / fname
                download_file(url, str(dest), expected_size=size)
                if not validate_zip_integrity(dest):
                    raise ValueError(f"Corrupt ZIP: {fname}")
                with tempfile.TemporaryDirectory() as tmpdir:
                    with zipfile.ZipFile(dest, "r") as zf:
                        zf.extractall(tmpdir)
                    process_extracted_files(tmpdir, latest, ftype)
            console.print("[green]Custom installation complete.[/]")
        else:
            download_and_process_package(latest, package)
        console.print("[green]Dataset installation complete![/]")
    except Exception as e:
        console.print(f"[red]Installation failed: {e}[/]")
    Prompt.ask("Press Enter to continue")


def db_stats():
    from app.database import get_connection

    conn = get_connection()
    companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    plans = conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
    providers = conn.execute("SELECT COUNT(*) FROM service_providers").fetchone()[0]
    console.print(f"Companies: {companies}")
    console.print(f"Plans: {plans}")
    console.print(f"Service Providers: {providers}")
    Prompt.ask("Press Enter to continue")


def config_menu():
    console.print(
        "Configuration editing not implemented in CLI. Edit config/config.json directly."
    )
    Prompt.ask("Press Enter to continue")


def export_menu():
    console.print("Export last result (if any) will be saved.")
    console.print("[yellow]No previous result in memory.[/]")
    Prompt.ask("Press Enter to continue")


# Alias for backward compatibility
run_interactive = main_menu