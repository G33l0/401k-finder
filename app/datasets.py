"""
Dataset handling: discovery, download, extraction, import, manifest.
Maintains backward compatibility with existing CLI functions.
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
from app.dol_datasets import discover_datasets, get_dataset_links
from app.downloader import download_file, sha256_file
from app.validation import validate_zip_integrity
from app.utils import human_readable_size, get_free_disk_space
from app.models import insert_company, insert_plan, insert_service_provider, record_dataset_file
from app.database import get_connection

logger = logging.getLogger(__name__)

MANIFEST_FILE = "data/metadata/datasets.json"

# ---------------------------------------------------------------------------
# Manifest handling
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
    metadata = discover_datasets()
    if not metadata or 'datasets' not in metadata:
        return None
    catalog = {}
    for year_str, files in metadata['datasets'].items():
        year = int(year_str)
        catalog[year] = []
        for f in files:
            size = f.get('compressed_size') or f.get('size')
            catalog[year].append((f['name'], f['url'], size))
    return catalog

def get_latest_year(catalog):
    if not catalog:
        return None
    return max(catalog.keys())

def classify_file_type(filename, year):
    lower = filename.lower()
    if 'sf' in lower and 'private' in lower:
        return 'main_form5500'
    if 'sch-c' in lower or 'schedule_c' in lower:
        return 'schedule_c'
    if 'sch-a' in lower:
        return 'schedule_a'
    if 'sch-d' in lower:
        return 'schedule_d'
    if 'sch-g' in lower:
        return 'schedule_g'
    if 'sch-h' in lower:
        return 'schedule_h'
    if 'sch-i' in lower:
        return 'schedule_i'
    if 'sch-r' in lower:
        return 'schedule_r'
    return 'other'

def calculate_package_sizes(catalog, year, package='standard'):
    if year not in catalog:
        return None
    files = catalog[year]
    config = load_config()
    expansion = config.get('csv_expansion_factor', 8.0)
    selected = []
    for fname, url, size in files:
        ftype = classify_file_type(fname, year)
        if package == 'essential':
            if ftype in ('main_form5500', 'schedule_c'):
                selected.append((fname, url, size, ftype))
        elif package == 'standard':
            if ftype in ('main_form5500', 'schedule_c', 'schedule_a', 'schedule_d',
                         'schedule_g', 'schedule_h', 'schedule_i', 'schedule_r'):
                selected.append((fname, url, size, ftype))
        elif package == 'full':
            selected.append((fname, url, size, ftype))
    comp_total = sum(sz for _, _, sz, _ in selected if sz) if selected else 0
    extract_total = int(comp_total * expansion) if comp_total else 0
    db_estimate = int(extract_total * 0.8) if extract_total else 0
    return {
        'compressed': comp_total,
        'extracted': extract_total,
        'database': db_estimate,
        'temp_needed': extract_total + comp_total,
        'file_list': selected
    }

def download_and_process_package(year, package_type='essential'):
    config = load_config()
    catalog = fetch_dataset_catalog()
    if not catalog or year not in catalog:
        raise RuntimeError(f"Dataset year {year} not available.")
    sizes = calculate_package_sizes(catalog, year, package_type)
    if not sizes or not sizes['file_list']:
        raise RuntimeError("Selected package has no files.")
    safety_mb = config.get('storage_safety_margin_mb', 50) * 1024 * 1024
    required = sizes['temp_needed'] + sizes['database'] + safety_mb
    free = get_free_disk_space()
    if free is not None and free < required:
        raise RuntimeError(f"Insufficient disk space. Required: {human_readable_size(required)}, Available: {human_readable_size(free)}")
    raw_dir = Path(config['raw_dir']) / str(year)
    raw_dir.mkdir(parents=True, exist_ok=True)
    for fname, url, size, ftype in sizes['file_list']:
        dest = raw_dir / fname
        try:
            download_file(url, str(dest), expected_size=size)
            if not validate_zip_integrity(dest):
                raise ValueError("Corrupt ZIP")
            with tempfile.TemporaryDirectory() as tmpdir:
                with zipfile.ZipFile(dest, 'r') as zf:
                    zf.extractall(tmpdir)
                process_extracted_files(tmpdir, year, ftype)
            record_dataset_file(year, fname, ftype, compressed_size=size, extracted_size=None, source_url=url)
        except Exception as e:
            logger.error(f"Failed to process {fname}: {e}")
            if dest.exists():
                dest.unlink()
            raise
    conn = get_connection()
    conn.execute("INSERT OR REPLACE INTO dataset_versions (year, download_date, record_count) VALUES (?, datetime('now'), 0)", (year,))
    conn.commit()
    return True

def process_extracted_files(directory, year, file_type):
    csv_files = list(Path(directory).glob('**/*.csv'))
    if not csv_files:
        logger.warning(f"No CSV found in {directory}")
        return
    for csv_file in csv_files:
        fname = csv_file.name.lower()
        if 'f_5500' in fname or 'form_5500' in fname:
            import_form5500_csv(str(csv_file), year)
        elif 'sch_c' in fname or 'schedule_c' in fname:
            import_schedule_c_csv(str(csv_file), year)

# ---------------------------------------------------------------------------
# New DOL dataset pipeline
# ---------------------------------------------------------------------------
def download_dataset(year, dataset_type='latest', force=False):
    config = load_config()
    links = get_dataset_links(year)
    if not links:
        raise RuntimeError(f"No dataset links found for year {year}")
    if dataset_type == 'latest':
        selected = next((l for l in links if l.get('file_type') == 'latest' and 'zip' in l['name'].lower()), links[0])
    elif dataset_type == 'all':
        selected = next((l for l in links if l.get('file_type') == 'all' and 'zip' in l['name'].lower()), links[0])
    else:
        selected = links[0]
    url = selected['url']
    filename = selected['name']
    download_dir = Path(config['raw_dir']) / str(year)
    download_dir.mkdir(parents=True, exist_ok=True)
    dest_path = download_dir / filename
    if dest_path.exists() and not force:
        print(f"Dataset file already exists: {dest_path}")
        return str(dest_path), selected
    print(f"Downloading {url} ...")
    expected_size = selected.get('size')
    download_file(url, str(dest_path), expected_size=expected_size)
    if not validate_zip_integrity(dest_path):
        dest_path.unlink(missing_ok=True)
        raise ValueError("Downloaded file is not a valid ZIP archive")
    checksum = sha256_file(dest_path)
    size = os.path.getsize(dest_path)
    add_to_manifest(year=year, dataset_type=dataset_type, source='DOL',
                    catalog_url=config.get('dol_index_url'), download_url=url,
                    filename=filename, size_bytes=size, sha256=checksum,
                    status='downloaded')
    return str(dest_path), selected

def extract_dataset(zip_path, year):
    config = load_config()
    extract_dir = Path(config['raw_dir']) / str(year) / 'extracted'
    extract_dir.mkdir(parents=True, exist_ok=True)
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            for member in zf.namelist():
                if member.startswith('/') or '..' in member.split('/'):
                    raise ValueError(f"Unsafe path in ZIP: {member}")
            zf.extractall(extract_dir)
    except Exception as e:
        shutil.rmtree(extract_dir, ignore_errors=True)
        raise
    return extract_dir

def import_csv_to_db(csv_path, year):
    fname = Path(csv_path).name.lower()
    if 'f_5500' in fname or 'form_5500' in fname:
        import_form5500_csv(str(csv_path), year)
    elif 'sch_c' in fname or 'schedule_c' in fname:
        import_schedule_c_csv(str(csv_path), year)

def build_database(year, dataset_type='latest', force=False):
    zip_path, link = download_dataset(year, dataset_type, force=force)
    extract_dir = extract_dataset(zip_path, year)
    csv_files = list(extract_dir.rglob('*.csv'))
    if not csv_files:
        raise RuntimeError("No CSV files found in extracted dataset")
    print(f"Found {len(csv_files)} CSV files. Importing...")
    for csv_file in csv_files:
        import_csv_to_db(csv_file, year)
    add_to_manifest(year=year, dataset_type=dataset_type, source='DOL',
                    catalog_url=load_config().get('dol_index_url'),
                    download_url=link['url'], filename=link['name'],
                    size_bytes=os.path.getsize(zip_path),
                    sha256=sha256_file(zip_path), status='active')
    print("Database build complete.")

def import_dataset_from_file(file_path, year):
    config = load_config()
    dest = Path(config['raw_dir']) / str(year)
    dest.mkdir(parents=True, exist_ok=True)
    shutil.copy2(file_path, dest / Path(file_path).name)
    zip_path = dest / Path(file_path).name
    extract_dir = extract_dataset(zip_path, year)
    csv_files = list(extract_dir.rglob('*.csv'))
    for csv_file in csv_files:
        import_csv_to_db(csv_file, year)
    print("Import complete.")

# ---------------------------------------------------------------------------
# CSV import functions
# ---------------------------------------------------------------------------
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

def check_and_update_datasets():
    """Check for dataset updates and prompt user."""
    print("Checking for dataset updates...")
    from app.dol_datasets import discover_datasets
    metadata = discover_datasets(force_refresh=True)
    if metadata:
        latest = metadata.get('latest_year')
        print(f"Latest available dataset year: {latest}")
        # Add update logic here if needed
    else:
        print("Could not check updates.")