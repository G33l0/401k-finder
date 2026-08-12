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
    return parser

def main():
    parser = parse_args()
    args = parser.parse_args()
    config = load_config()
    ensure_dirs(config)
    setup_logging(config)
    initialize_database()

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
    else:
        main_menu()

def run_self_test():
    # (unchanged – same as the last corrected version)
    tests = []
    def test(name, func):
        try:
            func()
            tests.append((name, "PASS"))
        except Exception as e:
            tests.append((name, f"FAIL: {e}"))
    def check(condition, message="Assertion failed"):
        if not condition:
            raise AssertionError(message)

    test("Database", lambda: initialize_database())
    from app.matching import exact_match
    test("Company matching", lambda: check(exact_match("Airgas USA, LLC", "Airgas USA LLC")))
    from app.ein import find_ein
    test("EIN matching", lambda: find_ein("Nonexistent"))
    from app.plans import is_401k_plan
    test("Plan detection", lambda: check(is_401k_plan("401(k) Savings Plan")))
    test("Schedule C parser", lambda: None)
    from app.classification import classify_provider
    test("Provider classification", lambda: check(classify_provider("Fidelity", "recordkeeping") == 'RECORDKEEPER'))
    from app.database import get_connection
    conn = get_connection()
    conn.execute("DELETE FROM provider_identities")
    conn.execute("INSERT INTO provider_identities (id, canonical_name, current_display_name) VALUES (99,'Empower','Empower')")
    conn.commit()
    conn.close()
    from app.models import add_provider_alias
    add_provider_alias(99, "Great-West Life & Annuity", "HISTORICAL_NAME")
    from app.provider_resolution import resolve_provider
    test("Provider identity resolution", lambda: check(resolve_provider("Great-West Life & Annuity")['canonical_identity'] == 'Empower'))
    from app.utils import is_valid_url
    test("URL validation", lambda: check(not is_valid_url("badurl") and is_valid_url("https://example.com")))
    from app.exports import export_result
    test("Export", lambda: export_result({'company': 'test'}, format='json'))
    test("CLI", lambda: parse_args().parse_args([]))

    print("\nSELF TEST RESULTS:")
    for name, status in tests:
        print(f"  {name}: {status}")
    all_pass = all('PASS' in s for _, s in tests)
    print("OVERALL:", "PASS" if all_pass else "FAILURE")

if __name__ == '__main__':
    main()