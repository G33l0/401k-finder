#!/usr/bin/env python3
"""401K Provider Finder - Main entry point."""
import sys
import argparse
import json
import logging
from app.cli import main_menu, first_run_installer
from app.config import load_config, ensure_dirs
from app.logging_config import setup_logging
from app.database import initialize_database, get_connection
from app.health import run_health_check
from app.search import perform_search, search_provider, search_ein, search_history
from app.exports import export_result
from app.datasets import check_and_update_datasets, build_database, import_dataset_from_file
from app.dol_datasets import discover_datasets, run_dol_diagnostics

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
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    parser.add_argument('--discover-datasets', action='store_true', help='Discover available DOL datasets')
    parser.add_argument('--dataset-status', action='store_true', help='Show dataset installation status')
    parser.add_argument('--download-dataset', type=int, metavar='YEAR', help='Download dataset for a specific year')
    parser.add_argument('--import-dataset', metavar='PATH', help='Import a local dataset ZIP file')
    parser.add_argument('--build-database', type=int, metavar='YEAR', help='Build SQLite database for a year')
    parser.add_argument('--verify-dataset', type=int, metavar='YEAR', help='Verify dataset integrity for a year')
    return parser

def main():
    parser = parse_args()
    args = parser.parse_args()

    # Setup logging
    config = load_config()
    ensure_dirs(config)
    if args.debug:
        config['log_level'] = 'DEBUG'
    setup_logging(config)
    logger = logging.getLogger(__name__)
    logger.debug("Starting 401K Provider Finder")

    initialize_database()

    if args.test_dol:
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

    if args.discover_datasets:
        metadata = discover_datasets(force_refresh=True)
        print(json.dumps(metadata, indent=2))
        sys.exit(0)

    if args.dataset_status:
        from app.datasets import load_manifest
        manifest = load_manifest()
        print(json.dumps(manifest, indent=2))
        sys.exit(0)

    if args.download_dataset:
        year = args.download_dataset
        from app.datasets import download_dataset
        path, link = download_dataset(year, 'latest')
        print(f"Downloaded to {path}")
        sys.exit(0)

    if args.import_dataset:
        file_path = args.import_dataset
        year = args.year or 2025
        import_dataset_from_file(file_path, year)
        print(f"Imported {file_path} for year {year}")
        sys.exit(0)

    if args.build_database:
        year = args.build_database
        build_database(year, 'latest', force=True)
        sys.exit(0)

    if args.verify_dataset:
        year = args.verify_dataset
        from app.datasets import load_manifest, sha256_file
        manifest = load_manifest()
        datasets = [d for d in manifest['datasets'] if d['year'] == year]
        if not datasets:
            print(f"No dataset manifest entry for {year}")
            sys.exit(1)
        # Check files exist and hash matches
        from pathlib import Path
        config = load_config()
        for d in datasets:
            file_path = Path(config['raw_dir']) / str(year) / d['filename']
            if not file_path.exists():
                print(f"FAIL: {file_path} missing")
                sys.exit(1)
            actual_hash = sha256_file(file_path)
            if actual_hash != d['sha256']:
                print(f"FAIL: checksum mismatch for {d['filename']}")
                sys.exit(1)
        print(f"Dataset {year}: OK")
        sys.exit(0)

    # Existing commands...
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
        # ... existing search logic
        pass
    if args.provider:
        # ... existing provider search
        pass

    # Interactive mode
    conn = get_connection()
    row = conn.execute("SELECT COUNT(*) FROM plans").fetchone()
    if row[0] == 0:
        first_run_installer()
        main_menu()
    else:
        main_menu()

if __name__ == '__main__':
    main()