#!/usr/bin/env python3
"""401K Provider Finder - Main entry point."""
import sys
import argparse
from app.cli import main_menu, first_run_installer
from app.config import load_config, ensure_dirs
from app.logging_config import setup_logging
from app.database import initialize_database, get_connection
from app.health import run_health_check
from app.search import perform_search, search_provider, search_ein, search_history
from app.exports import export_result
from app.datasets import check_and_update_datasets

def parse_args():
    parser = argparse.ArgumentParser(description="401K Provider Finder")
    parser.add_argument('--company', help='Company name to search')
    parser.add_argument('--year', type=int, help='Plan year')
    parser.add_argument('--ein', action='store_true', help='Find EIN for company')
    parser.add_argument('--history', action='store_true', help='Show provider history for company')
    parser.add_argument('--provider', help='Search provider directory')
    parser.add_argument('--json', action='store_true', help='Output as JSON')
    parser.add_argument('--health', action='store_true', help='Run health check')
    parser.add_argument('--update', action='store_true', help='Check and download dataset updates')
    parser.add_argument('--self-test', action='store_true', help='Run self diagnostic')
    parser.add_argument('--test-dol', action='store_true', help='Test DOL dataset connectivity')
    return parser

def main():
    parser = parse_args()
    args = parser.parse_args()
    config = load_config()
    ensure_dirs(config)
    setup_logging(config)
    initialize_database()

    if args.test_dol:
        from app.dol_datasets import run_dol_diagnostics
        diag = run_dol_diagnostics()
        print("DOL CONNECTION TEST")
        print(f"DNS:                 {'PASS' if diag['dns'] else 'FAIL'}")
        print(f"TLS:                 {'PASS' if diag['tls'] else 'FAIL'}")
        print(f"HTTP:                {'PASS' if diag['http'] else 'FAIL'}")
        print(f"DOL PAGE:            {'PASS' if diag['page'] else 'FAIL'}")
        print(f"DATASET DISCOVERY:   {'PASS' if diag['discovery'] else 'FAIL'}")
        print(f"LATEST YEAR:         {diag.get('latest_year') or 'N/A'}")
        print(f"DATASET FILES:       {diag.get('file_count')}")
        print(f"CACHE:               {'PASS' if diag['cache'] else 'N/A'}")
        if diag.get('error'):
            print(f"ERROR: {diag['error']}")
        sys.exit(0)

    if args.self_test:
        run_self_test()
        sys.exit(0)

    if args.health:
        run_health_check()
        sys.exit(0)

    if args.update:
        check_and_update_datasets()
        sys.exit(0)

    if args.company:
        if args.ein:
            result = search_ein(args.company)
        elif args.history:
            result = search_history(args.company)
        else:
            year = args.year or 2025
            result = perform_search(args.company, year)
        if args.json:
            import json
            print(json.dumps(result, indent=2))
        else:
            export_result(result, format='txt')
        sys.exit(0)

    if args.provider:
        from app.models import search_provider_directory
        providers = search_provider_directory(args.provider)
        import json
        print(json.dumps([dict(p) for p in providers], indent=2))
        sys.exit(0)

    # Interactive mode – check for first run
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) FROM plans").fetchone()
    if row[0] == 0:
        first_run_installer()
        # After installer returns (user chose offline/skip or completed install),
        # enter the main menu.
        main_menu()
    else:
        main_menu()

def run_self_test():
    # ... unchanged ...
    pass

if __name__ == '__main__':
    main()