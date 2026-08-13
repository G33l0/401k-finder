"""
Dataset handling: discovery, download, extraction, import, manifest.
Uses static 2025 catalog and layout files for correct import.
"""
import csv
import json
import logging
import os
import shutil
import time
import zipfile
import tempfile
from pathlib import Path

from app.config import load_config
from app.dol_datasets import STATIC_CATALOG, get_dataset_links
from app.downloader import download_file, sha256_file
from app.validation import validate_zip_integrity
from app.utils import human_readable_size, get_free_disk_space
from app.database import get_connection

logger = logging.getLogger(__name__)
MANIFEST_FILE = "data/metadata/datasets.json"

# ---------------------------------------------------------------------------
# Manifest handling (unchanged)
# ---------------------------------------------------------------------------
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

# ---------------------------------------------------------------------------
# Backward-compatible functions used by app/cli.py
# ---------------------------------------------------------------------------
def fetch_dataset_catalog():
    """Return catalog of years -> list of (filename, url, size) tuples."""
    links = get_dataset_links()
    catalog = {}
    for link in links:
        year = link['year']
        catalog.setdefault(year, []).append((link['name'], link['url'], link.get('compressed_size')))
    return catalog

def get_latest_year(catalog):
    if not catalog:
        return None
    years = [y for y in catalog.keys() if 1990 <= y <= 2100]
    return max(years) if years else None

def classify_file_type(filename, year=None):
    lower = filename.lower()
    if 'f_5500_sf' in lower:
        return 'form_5500_sf'
    if 'f_5500' in lower:
        return 'form_5500'
    if 'f_sch_a' in lower:
        return 'schedule_a'
    if 'f_sch_c' in lower:
        return 'schedule_c'
    if 'f_sch_d' in lower:
        return 'schedule_d'
    if 'f_sch_h' in lower:
        return 'schedule_h'
    if 'f_sch_i' in lower:
        return 'schedule_i'
    if 'f_sch_r' in lower:
        return 'schedule_r'
    return 'other'

def calculate_package_sizes(catalog, year, package='standard'):
    """Return files selected for package."""
    links = get_dataset_links(year)
    selected = []
    for link in links:
        ftype = link.get('file_type', classify_file_type(link['name'], year))
        if package == 'essential':
            if ftype in ('form_5500', 'form_5500_sf', 'schedule_r'):
                selected.append((link['name'], link['url'], link.get('compressed_size'), ftype))
        elif package == 'standard':
            if ftype in ('form_5500', 'form_5500_sf', 'schedule_r', 'schedule_a', 'schedule_c', 'schedule_d', 'schedule_h', 'schedule_i'):
                selected.append((link['name'], link['url'], link.get('compressed_size'), ftype))
        elif package == 'full':
            selected.append((link['name'], link['url'], link.get('compressed_size'), ftype))
    comp_total = sum(sz for _, _, sz, _ in selected if sz) if selected else 0
    extract_total = int(comp_total * 8.0) if comp_total else 0
    db_estimate = int(extract_total * 0.8) if extract_total else 0
    return {
        'compressed': comp_total,
        'extracted': extract_total,
        'database': db_estimate,
        'temp_needed': extract_total + comp_total,
        'file_list': selected
    }

def download_and_process_package(year, package_type='essential'):
    """Download selected package, extract, import."""
    config = load_config()
    sizes = calculate_package_sizes(None, year, package_type)
    if not sizes or not sizes['file_list']:
        raise RuntimeError("No files selected for this package.")
    raw_dir = Path(config['raw_dir']) / str(year)
    raw_dir.mkdir(parents=True, exist_ok=True)

    # Download layout files first
    for fname, url, size, ftype in sizes['file_list']:
        link = next((l for l in get_dataset_links(year) if l['name'] == fname), None)
        if link and 'layout_url' in link:
            layout_path = raw_dir / (fname.replace('.zip', '_layout.txt'))
            if not layout_path.exists():
                print(f"Downloading layout for {fname}...")
                download_file(link['layout_url'], str(layout_path), expected_size=None)
    # Download ZIPs
    for fname, url, size, ftype in sizes['file_list']:
        dest = raw_dir / fname
        if dest.exists() and validate_zip_integrity(dest):
            print(f"{fname} already installed.")
            continue
        print(f"Downloading {fname}...")
        download_file(url, str(dest), expected_size=size)
        if not validate_zip_integrity(dest):
            raise ValueError(f"Corrupt ZIP: {fname}")
    # Extract and import
    for fname, url, size, ftype in sizes['file_list']:
        dest = raw_dir / fname
        extract_dir = raw_dir / 'extracted' / fname.replace('.zip', '')
        extract_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(dest, 'r') as zf:
            zf.extractall(extract_dir)
        layout_file = raw_dir / (fname.replace('.zip', '_layout.txt'))
        process_extracted_files(extract_dir, year, ftype, layout_file)
    print("Package processed successfully.")

def process_extracted_files(directory, year, file_type, layout_file=None):
    """
    Process CSV files extracted from a ZIP.
    """
    csv_files = list(Path(directory).rglob('*.csv'))
    if not csv_files:
        logger.warning(f"No CSV found in {directory}")
        return
    for csv_file in csv_files:
        # Skip layout files (they are .txt, but just in case)
        if csv_file.suffix.lower() != '.csv':
            continue
        import_csv_with_layout(csv_file, year, layout_file, file_type)

def import_csv_with_layout(csv_path, year, layout_file, ftype):
    """Import CSV using layout file to map fields."""
    field_map = parse_layout_file(layout_file) if layout_file and Path(layout_file).exists() else {}
    if ftype.startswith('form_5500'):
        import_form5500_csv(csv_path, year, field_map)
    elif ftype == 'schedule_c':
        import_schedule_c_csv(csv_path, year, field_map)
    else:
        logger.info(f"Skipping import for {ftype}")

def parse_layout_file(layout_path):
    """Parse DOL layout file to extract field names (if needed)."""
    mapping = {}
    try:
        with open(layout_path, 'r', encoding='utf-8') as f:
            for line in f:
                parts = line.strip().split(',')
                if len(parts) >= 2:
                    pos = parts[0].strip()
                    field_name = parts[1].strip()
                    if field_name and pos.isdigit():
                        mapping[field_name] = int(pos)
    except Exception as e:
        logger.warning(f"Failed to parse layout {layout_path}: {e}")
    return mapping

def import_form5500_csv(filepath, year, field_map=None):
    """
    Import Form 5500 / 5500-SF data.
    Uses a single connection for all inserts.
    """
    from app.utils import normalize_company_name
    conn = get_connection()
    cursor = conn.cursor()
    count = 0
    try:
        with open(filepath, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            for row in reader:
                ein = row.get('SPONSOR_DFE_EIN') or row.get('SPONSOR_EIN') or row.get('EIN')
                sponsor = row.get('SPONSOR_DFE_NAME') or row.get('SPONSOR_NAME') or row.get('NAME')
                plan_name = row.get('PLAN_NAME')
                plan_number = row.get('PLAN_NUMBER') or row.get('PLAN_NUM')
                ack_id = row.get('ACK_ID')
                plan_type = row.get('PLAN_TYPE_CODE') or row.get('PLAN_CHAR_CODE') or ''
                if not (ein and sponsor and plan_name and ack_id):
                    continue
                norm = normalize_company_name(sponsor)
                cursor.execute("INSERT OR IGNORE INTO companies (name, normalized_name, ein) VALUES (?,?,?)",
                               (sponsor.strip(), norm, ein))
                # Get company id
                cursor.execute("SELECT id FROM companies WHERE ein=? LIMIT 1", (ein,))
                company_row = cursor.fetchone()
                if company_row:
                    company_id = company_row['id']
                    cursor.execute("INSERT OR IGNORE INTO plans (company_id, plan_name, plan_number, plan_type, plan_year, ein, filing_id, dataset_year) VALUES (?,?,?,?,?,?,?,?)",
                                   (company_id, plan_name.strip(), plan_number, plan_type, year, ein, ack_id, year))
                count += 1
        conn.commit()
        logger.info(f"Imported {count} rows from {filepath}")
    except Exception as e:
        logger.error(f"Form 5500 import error for {filepath}: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def import_schedule_c_csv(filepath, year, field_map=None):
    """
    Import Schedule C service provider data.
    """
    from app.schedule_c import parse_schedule_c
    conn = get_connection()
    cursor = conn.cursor()
    plans = {}
    try:
        # Build plan map from existing plans
        cursor.execute("SELECT id, ein, plan_number FROM plans WHERE dataset_year=?", (year,))
        for p in cursor.fetchall():
            if p['ein'] and p['plan_number']:
                plans[(p['ein'], p['plan_number'])] = p['id']
    except Exception as e:
        logger.error(f"Schedule C plan map error: {e}")
        conn.close()
        return

    # Use the single connection for parsing
    try:
        parse_schedule_c(filepath, plans, conn)
        conn.commit()
        logger.info(f"Schedule C imported from {filepath}")
    except Exception as e:
        logger.error(f"Schedule C import error: {e}")
        conn.rollback()
        raise
    finally:
        conn.close()

def download_dataset(year, dataset_type='all', force=False):
    """Download all dataset files for a given year."""
    links = get_dataset_links(year)
    if not links:
        raise RuntimeError("No dataset links found")
    config = load_config()
    raw_dir = Path(config['raw_dir']) / str(year)
    raw_dir.mkdir(parents=True, exist_ok=True)
    for link in links:
        dest = raw_dir / link['name']
        if dest.exists() and validate_zip_integrity(dest) and not force:
            print(f"{link['name']} already installed.")
            continue
        print(f"Downloading {link['name']}...")
        download_file(link['url'], str(dest), expected_size=link.get('compressed_size'))
        if not validate_zip_integrity(dest):
            raise ValueError(f"Corrupt ZIP: {link['name']}")
    return str(raw_dir), links

def build_database(year, dataset_type='all', force=False):
    """Download all, extract, import, mark active."""
    raw_dir, links = download_dataset(year, dataset_type, force)
    download_and_process_package(year, 'full')
    add_to_manifest(year=year, dataset_type=dataset_type, source='DOL',
                    catalog_url='', download_url='',
                    filename='all', size_bytes=0, sha256='', status='active')
    print("Database build complete.")

def import_dataset_from_file(file_path, year):
    """Import a local ZIP file."""
    config = load_config()
    raw_dir = Path(config['raw_dir']) / str(year)
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / Path(file_path).name
    shutil.copy2(file_path, dest)
    if not validate_zip_integrity(dest):
        raise ValueError("Invalid ZIP")
    extract_dir = raw_dir / 'extracted' / Path(file_path).stem
    extract_dir.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(dest, 'r') as zf:
        zf.extractall(extract_dir)
    ftype = classify_file_type(dest.name, year)
    process_extracted_files(extract_dir, year, ftype)
    print("Import complete.")

def check_and_update_datasets():
    print("Using static 2025 dataset catalog. No live update check.")