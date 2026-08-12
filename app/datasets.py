"""
Dataset handling: discovery, download, extraction, import, manifest.
"""
import csv
import json
import logging
import os
import shutil
import sqlite3
import tempfile
import zipfile
from pathlib import Path
from app.config import load_config
from app.dol_datasets import discover_datasets, get_dataset_links
from app.downloader import download_file, sha256_file
from app.validation import validate_zip_integrity
from app.utils import human_readable_size, get_free_disk_space
from app.models import insert_company, insert_plan, insert_service_provider
from app.database import get_connection

logger = logging.getLogger(__name__)

MANIFEST_FILE = "data/metadata/datasets.json"


def load_manifest():
    if os.path.exists(MANIFEST_FILE):
        try:
            with open(MANIFEST_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return {"datasets": []}


def save_manifest(manifest):
    os.makedirs(os.path.dirname(MANIFEST_FILE), exist_ok=True)
    with open(MANIFEST_FILE, 'w') as f:
        json.dump(manifest, f, indent=2)


def add_to_manifest(year, dataset_type, source, catalog_url, download_url,
                    filename, size_bytes, sha256, status):
    manifest = load_manifest()
    # Remove existing entry with same year/type
    manifest['datasets'] = [
        d for d in manifest['datasets']
        if not (d['year'] == year and d['dataset_type'] == dataset_type)
    ]
    manifest['datasets'].append({
        'year': year,
        'dataset_type': dataset_type,
        'source': source,
        'catalog_url': catalog_url,
        'download_url': download_url,
        'filename': filename,
        'downloaded_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'sha256': sha256,
        'size_bytes': size_bytes,
        'status': status
    })
    save_manifest(manifest)


def download_dataset(year, dataset_type='latest', force=False):
    """Download the dataset for a given year. Returns (file_path, metadata)."""
    config = load_config()
    links = get_dataset_links(year)
    if not links:
        raise RuntimeError(f"No dataset links found for year {year}")
    # Filter by type
    if dataset_type == 'latest':
        selected = next((l for l in links if l['file_type'] == 'latest' and 'zip' in l['name'].lower()), links[0])
    elif dataset_type == 'all':
        selected = next((l for l in links if l['file_type'] == 'all' and 'zip' in l['name'].lower()), links[0])
    else:
        selected = links[0]  # custom or specific file type

    url = selected['url']
    filename = selected['name']
    download_dir = Path(config['raw_dir']) / str(year)
    download_dir.mkdir(parents=True, exist_ok=True)
    dest_path = download_dir / filename

    # Check existing
    if dest_path.exists() and not force:
        print(f"Dataset file already exists: {dest_path}")
        return str(dest_path), selected

    # Download
    print(f"Downloading {url} ...")
    expected_size = selected.get('size')
    download_file(url, str(dest_path), expected_size=expected_size)

    # Validate archive
    if not validate_zip_integrity(dest_path):
        dest_path.unlink(missing_ok=True)
        raise ValueError("Downloaded file is not a valid ZIP archive")

    # Calculate checksum
    checksum = sha256_file(dest_path)
    size = os.path.getsize(dest_path)

    # Add to manifest
    add_to_manifest(
        year=year,
        dataset_type=dataset_type,
        source='DOL',
        catalog_url=config.get('dol_index_url'),
        download_url=url,
        filename=filename,
        size_bytes=size,
        sha256=checksum,
        status='downloaded'
    )
    return str(dest_path), selected


def extract_dataset(zip_path, year):
    """Safely extract ZIP into data/raw/<year>/extracted/."""
    config = load_config()
    extract_dir = Path(config['raw_dir']) / str(year) / 'extracted'
    extract_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            # Validate no path traversal
            for member in zf.namelist():
                if member.startswith('/') or '..' in member.split('/'):
                    raise ValueError(f"Unsafe path in ZIP: {member}")
            zf.extractall(extract_dir)
    except Exception as e:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise
    return extract_dir


def import_csv_to_db(csv_path, year):
    """Import a single CSV file into the database."""
    from app.datasets import import_form5500_csv, import_schedule_c_csv
    fname = Path(csv_path).name.lower()
    if 'f_5500' in fname or 'form_5500' in fname:
        import_form5500_csv(str(csv_path), year)
    elif 'sch_c' in fname or 'schedule_c' in fname:
        import_schedule_c_csv(str(csv_path), year)
    else:
        # Try generic import if fields match
        pass


def build_database(year, dataset_type='latest', force=False):
    """Download, extract, import, and mark dataset active."""
    zip_path, link = download_dataset(year, dataset_type, force=force)
    extract_dir = extract_dataset(zip_path, year)

    # Find CSVs and import
    csv_files = list(extract_dir.rglob('*.csv'))
    if not csv_files:
        raise RuntimeError("No CSV files found in extracted dataset")
    print(f"Found {len(csv_files)} CSV files. Importing...")
    for csv_file in csv_files:
        import_csv_to_db(csv_file, year)

    # Mark active in manifest
    add_to_manifest(
        year=year,
        dataset_type=dataset_type,
        source='DOL',
        catalog_url=load_config().get('dol_index_url'),
        download_url=link['url'],
        filename=link['name'],
        size_bytes=os.path.getsize(zip_path),
        sha256=sha256_file(zip_path),
        status='active'
    )
    print("Database build complete.")


def import_dataset_from_file(file_path, year):
    """Import a locally provided ZIP file."""
    config = load_config()
    dest = Path(config['raw_dir']) / str(year)
    dest.mkdir(parents=True, exist_ok=True)
    # Copy to standard location
    shutil.copy2(file_path, dest / Path(file_path).name)
    # Extract and import
    zip_path = dest / Path(file_path).name
    extract_dir = extract_dataset(zip_path, year)
    csv_files = list(extract_dir.rglob('*.csv'))
    for csv_file in csv_files:
        import_csv_to_db(csv_file, year)
    print("Import complete.")


# ============ Existing CSV import functions (kept from original) ============
def import_form5500_csv(filepath, year):
    from app.utils import normalize_company_name
    conn = get_connection()
    cursor = conn.cursor()
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                sponsor_name = row.get('SPONSOR_DFE_NAME') or row.get('SPONS_DFE_NAME') or row.get('SPONSOR_NAME')
                ein = row.get('SPONSOR_DFE_EIN') or row.get('SPONS_DFE_EIN') or row.get('SPONSOR_EIN')
                plan_name = row.get('PLAN_NAME')
                plan_number = row.get('PLAN_NUMBER') or row.get('PLAN_NUM')
                ack_id = row.get('ACK_ID')
                plan_type = row.get('PLAN_TYPE_CODE') or row.get('PLAN_CHAR_CODE')
                if not (sponsor_name and ein and plan_name and ack_id):
                    continue
                norm = normalize_company_name(sponsor_name)
                cursor.execute("INSERT OR IGNORE INTO companies (name, normalized_name, ein) VALUES (?,?,?)",
                               (sponsor_name.strip(), norm, ein))
                conn.commit()
                company = cursor.execute("SELECT id FROM companies WHERE ein=? LIMIT 1", (ein,)).fetchone()
                if company:
                    insert_plan(company['id'], plan_name.strip(), plan_number, plan_type, year, ein, ack_id, year)
    except Exception as e:
        logger.error(f"Form 5500 import error: {e}")
        raise
    conn.close()

def import_schedule_c_csv(filepath, year):
    from app.schedule_c import parse_schedule_c
    conn = get_connection()
    plans = conn.execute("SELECT id, ein, plan_number FROM plans WHERE dataset_year=?", (year,)).fetchall()
    plan_map = {(p['ein'], p['plan_number']): p['id'] for p in plans if p['ein'] and p['plan_number']}
    parse_schedule_c(filepath, plan_map)
    conn.close()