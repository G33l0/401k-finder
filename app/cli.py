import sys
import os
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
    add_provider_alias,
)
from app.datasets import (
    fetch_dataset_catalog,
    get_latest_year,
    calculate_package_sizes,
    download_and_process_package,
    classify_file_type,
    process_extracted_files,
)
from app.exports import export_result
from app.health import run_health_check
from app.utils import human_readable_size, get_free_disk_space
from app.config import load_config

console = Console()

def show_banner():
    console.print(Panel.fit(
        "[bold cyan]401K PROVIDER FINDER[/]\n"
        "[dim]U.S. Retirement Plan Research Tool[/]",
        border_style="bright_blue", box=box.ROUNDED
    ))

# ---------------- FIRST RUN INSTALLER ----------------
def first_run_installer():
    """Display the setup wizard when no dataset is installed."""
    console.clear()
    console.print(Panel.fit(
        "[bold cyan]401K PROVIDER FINDER - SETUP[/]\n"
        "[dim]No local Form 5500 dataset installed.[/]",
        border_style="bright_blue", box=box.ROUNDED
    ))

    catalog = fetch_dataset_catalog()
    if not catalog:
        console.print("[red]Unable to contact DOL dataset service and no cached metadata available.[/]")
        console.print("[yellow]Options:[/]")
        console.print("1. Retry")
        console.print("2. Offline Mode / Skip Download")
        console.print("0. Exit")
        choice = Prompt.ask("Choice", choices=["1", "2", "0"])
        if choice == "1":
            first_run_installer()   # retry
        elif choice == "2":
            return                  # continue to main menu without data
        else:
            sys.exit(0)
        return                      # important: skip the rest

    # Catalog exists – proceed with package selection
    latest = get_latest_year(catalog)
    console.print(f"Latest DOL dataset detected: [bold]{latest}[/]")
    console.print("\nSelect the data package you want to install:\n")
    console.print("1. ESSENTIAL – smallest, for basic 401(k) provider lookups")
    console.print("2. STANDARD – includes additional schedules (recommended)")
    console.print("3. FULL – complete dataset for the latest year")
    console.print("4. CUSTOM – choose individual datasets")
    console.print("5. OFFLINE / SKIP DOWNLOAD")
    console.print("0. Exit")
    choice = Prompt.ask("Enter choice", choices=[str(i) for i in range(6)])
    if choice == '0':
        sys.exit(0)
    if choice == '5':
        console.print("[yellow]Entering offline mode. You can install datasets later from Dataset Manager.[/]")
        return
    pkg_map = {'1': 'essential', '2': 'standard', '3': 'full', '4': 'custom'}
    package = pkg_map[choice]
    if package == 'custom':
        install_custom(catalog, latest)
    else:
        install_package(catalog, latest, package)


def install_package(catalog, year, package):
    """Show sizes and confirm, then download the selected package."""
    sizes = calculate_package_sizes(catalog, year, package)
    if not sizes or not sizes['file_list']:
        console.print("[red]No files available for this package.[/]")
        return
    config = load_config()
    safety_mb = config.get('storage_safety_margin_mb', 50)
    safety_bytes = safety_mb * 1024 * 1024
    required = sizes['temp_needed'] + sizes['database'] + safety_bytes
    free = get_free_disk_space()
    console.print(f"\n[bold]{package.upper()} PACKAGE[/]")
    console.print(f"Latest dataset: {year}")
    console.print("Files:")
    for fname, _, sz, ftype in sizes['file_list']:
        console.print(f"  • {fname} ({human_readable_size(sz) if sz else 'unknown size'})")
    console.print(f"\nCompressed download: {human_readable_size(sizes['compressed']) if sizes['compressed'] else 'unknown'}")
    console.print(f"Extracted size: ~{human_readable_size(sizes['extracted']) if sizes['extracted'] else 'unknown'}")
    console.print(f"Final database: ~{human_readable_size(sizes['database']) if sizes['database'] else 'unknown'}")
    console.print(f"Required free storage: {human_readable_size(required)}")
    if free:
        console.print(f"Available storage: {human_readable_size(free)}")
        if free < required:
            console.print("[red]ERROR: INSUFFICIENT STORAGE[/]")
            console.print(f"Required: {human_readable_size(required)}, Available: {human_readable_size(free)}")
            console.print("Select ESSENTIAL or CUSTOM instead.")
            return
    if not Confirm.ask("Proceed with download?"):
        return
    try:
        download_and_process_package(year, package)
        console.print(f"[green]{package.capitalize()} dataset installed successfully![/]")
        if Confirm.ask("Keep raw downloaded files?", default=False):
            console.print("Raw files kept.")
        else:
            import shutil
            raw_dir = Path(config['raw_dir']) / str(year)
            if raw_dir.exists():
                shutil.rmtree(raw_dir)
                console.print("Raw files removed.")
    except Exception as e:
        console.print(f"[red]Installation failed: {e}[/]")


def install_custom(catalog, year):
    """Let the user pick individual files."""
    files = catalog[year]
    selected = []
    for fname, url, size in files:
        ftype = classify_file_type(fname, year)
        sz_str = human_readable_size(size) if size else 'unknown'
        if Confirm.ask(f"Include {fname} ({sz_str})?", default=(ftype in ('main_form5500','schedule_c'))):
            selected.append((fname, url, size, ftype))
    if not selected:
        console.print("[yellow]No files selected.[/]")
        return
    comp_total = sum(sz for _, _, sz, _ in selected if sz) or 0
    extract_total = int(comp_total * 8.0) if comp_total else 0
    db_est = int(extract_total * 0.8) if extract_total else 0
    console.print(f"\nEstimated download: {human_readable_size(comp_total)}")
    console.print(f"Estimated extracted: ~{human_readable_size(extract_total)}")
    console.print(f"Estimated database: ~{human_readable_size(db_est)}")
    free = get_free_disk_space()
    if free:
        console.print(f"Available storage: {human_readable_size(free)}")
    if not Confirm.ask("Download selected files?"):
        return
    from app.downloader import download_file
    from app.validation import validate_zip_integrity
    config = load_config()
    raw_dir = Path(config['raw_dir']) / str(year)
    raw_dir.mkdir(parents=True, exist_ok=True)
    try:
        for fname, url, size, ftype in selected:
            dest = raw_dir / fname
            download_file(url, str(dest), expected_size=size)
            if not validate_zip_integrity(dest):
                raise ValueError(f"Corrupt ZIP: {fname}")
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(dest, 'r') as zf:
                    zf.extractall(tmpdir)
                process_extracted_files(tmpdir, year, ftype)
        console.print("[green]Custom installation complete.[/]")
    except Exception as e:
        console.print(f"[red]Installation failed: {e}[/]")


# ---------------- MAIN MENU ----------------
def main_menu():
    while True:
        console.clear()
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
            console.clear()
            find_provider_flow()
        elif choice == "2":
            console.clear()
            company_ein_flow()
        elif choice == "3":
            console.clear()
            historical_flow()
        elif choice == "4":
            console.clear()
            provider_directory_flow()
        elif choice == "5":
            console.clear()
            dataset_manager_menu()
        elif choice == "6":
            console.clear()
            db_stats()
        elif choice == "7":
            console.clear()
            config_menu()
        elif choice == "8":
            console.clear()
            run_health_check()
            Prompt.ask("Press Enter to return to main menu")
        elif choice == "9":
            console.clear()
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
    table.add_row("Plan Year", str(result.get("fallback_year", result.get("year", ""))))
    table.add_row("Provider (Filing)", result.get("recordkeeper_filing_name", ""))
    if "recordkeeper_identity" in result and result["recordkeeper_identity"]:
        table.add_row("Provider Identity", result["recordkeeper_identity"])
    if "recordkeeper_current" in result and result["recordkeeper_current"] != result.get("recordkeeper_identity"):
        table.add_row("Current Name", result["recordkeeper_current"])
    if "provider_login_url" in result:
        table.add_row("Provider Login", result["provider_login_url"])
    if "confidence" in result:
        conf = result["confidence"]
        overall = conf.get("overall", "N/A") if isinstance(conf, dict) else conf
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
    console.print("[yellow]Provider history timeline will be displayed when implemented fully.[/]")
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
                console.print(f"{r['legal_name']} | Login: {r['login_url']} | Phone: {r['phone']}")
        else:
            console.print("[red]Not found[/]")
    elif choice == "2":
        canonical = Prompt.ask("Canonical name")
        display = Prompt.ask("Display name (optional)", default="")
        domain = Prompt.ask("Domain (optional)")
        login = Prompt.ask("Login URL (optional)")
        phone = Prompt.ask("Phone (optional)")
        add_full_provider(canonical, display or canonical, display, domain, login, phone)
        console.print("[green]Provider identity added.[/]")
    elif choice == "3":
        identity_name = Prompt.ask("Canonical identity name")
        identity = get_provider_identity_by_name(identity_name)
        if not identity:
            console.print("[red]Identity not found.[/]")
            return
        console.print(f"Managing aliases for {identity['canonical_name']}")
        alias = Prompt.ask("Alias name")
        alias_type = Prompt.ask("Alias type",
                               choices=["FORM_5500_NAME","HISTORICAL_NAME","BRAND","LEGAL_ENTITY","OTHER"],
                               default="FORM_5500_NAME")
        add_provider_alias(identity["id"], alias, alias_type)
        console.print("[green]Alias added.[/]")
    Prompt.ask("Press Enter to continue")


def dataset_manager_menu():
    console.print("1. Install/Update Dataset (online)")
    console.print("2. Download Historical Dataset")
    console.print("3. Show Installed Datasets")
    console.print("4. Validate Datasets")
    console.print("5. Backup Database")
    console.print("6. Import Local Dataset (offline)")
    choice = Prompt.ask("Choice", choices=["1","2","3","4","5","6"])
    if choice == "1":
        first_run_installer()
    elif choice == "2":
        year_str = Prompt.ask("Year to download")
        try:
            year = int(year_str)
        except ValueError:
            console.print("[red]Invalid year[/]")
            Prompt.ask("Press Enter to continue")
            return
        package = Prompt.ask("Package (essential/standard/full)", choices=["essential","standard","full"], default="essential")
        catalog = fetch_dataset_catalog()
        if catalog and year in catalog:
            install_package(catalog, year, package)
        else:
            console.print(f"[red]Dataset year {year} not found.[/]")
    elif choice == "3":
        from app.database import get_connection
        conn = get_connection()
        years = conn.execute("SELECT DISTINCT dataset_year FROM plans ORDER BY dataset_year").fetchall()
        if years:
            console.print("Installed dataset years:", ", ".join(str(y["dataset_year"]) for y in years))
        else:
            console.print("[yellow]No datasets installed.[/]")
    elif choice == "4":
        console.print("Validation not yet implemented.")
    elif choice == "5":
        console.print("Backup not yet implemented.")
    elif choice == "6":
        import_local_dataset()
    Prompt.ask("Press Enter to continue")


def import_local_dataset():
    console.print("[bold]Import Local Dataset[/]")
    year_str = Prompt.ask("Dataset year")
    try:
        year = int(year_str)
    except ValueError:
        console.print("[red]Invalid year[/]")
        return
    config = load_config()
    raw_dir = Path(config["raw_dir"]) / str(year)
    if not raw_dir.exists():
        console.print(f"[red]Directory not found: {raw_dir}[/]")
        return
    zip_files = list(raw_dir.glob("*.zip"))
    csv_files = list(raw_dir.glob("*.csv"))
    if not zip_files and not csv_files:
        console.print("[red]No ZIP or CSV files found.[/]")
        return
    if zip_files:
        console.print(f"ZIP files: {len(zip_files)}")
    if csv_files:
        console.print(f"CSV files: {len(csv_files)}")
    if not Confirm.ask("Process these files?"):
        return
    for zf in zip_files:
        ftype = classify_file_type(zf.name, year)
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(zf, 'r') as z:
                    z.extractall(tmpdir)
                process_extracted_files(tmpdir, year, ftype)
            console.print(f"[green]{zf.name} imported.[/]")
        except Exception as e:
            console.print(f"[red]Failed {zf.name}: {e}[/]")
    for cf in csv_files:
        fname = cf.name.lower()
        try:
            if 'f_5500' in fname or 'form_5500' in fname:
                from app.datasets import import_form5500_csv
                import_form5500_csv(str(cf), year)
            elif 'sch_c' in fname or 'schedule_c' in fname:
                from app.datasets import import_schedule_c_csv
                import_schedule_c_csv(str(cf), year)
            console.print(f"[green]{cf.name} imported.[/]")
        except Exception as e:
            console.print(f"[red]Failed {cf.name}: {e}[/]")
    console.print("[green]Local import complete.[/]")


def db_stats():
    from app.database import get_connection
    conn = get_connection()
    companies = conn.execute("SELECT COUNT(*) FROM companies").fetchone()[0]
    plans = conn.execute("SELECT COUNT(*) FROM plans").fetchone()[0]
    providers = conn.execute("SELECT COUNT(*) FROM service_providers").fetchone()[0]
    console.print(f"Companies: {companies}")
    console.print(f"Plans: {plans}")
    console.print(f"Service Providers: {providers}")


def config_menu():
    console.print("Configuration editing not implemented in CLI. Edit config/config.json directly.")


def export_menu():
    console.print("Export last result (if any) will be saved.")
    console.print("[yellow]No previous result in memory.[/]")


run_interactive = main_menu