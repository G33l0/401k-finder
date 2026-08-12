import logging
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path

from app.config import load_config
from app.downloader import download_file
from app.validation import validate_zip_integrity
from app.utils import human_readable_size, get_free_disk_space
from app.models import record_dataset_file
from app.database import get_connection
from app.dol_datasets import discover_datasets

logger = logging.getLogger(__name__)


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
            catalog[year].append((f['name'], f['url'], f.get('compressed_size')))
    return catalog


def get_latest_year(catalog):
    if not catalog:
        return None
    return max(catalog.keys())


def classify_file_type(filename, year):
    """Heuristically determine the dataset type from the filename."""
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
    """Return estimated sizes and file list for a package."""
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
        # 'custom' handled separately
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
    """Download, validate, and process a full package."""
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
    """Process CSV files extracted from a ZIP."""
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


def import_form5500_csv(filepath, year):
    """Import Form 5500 main data from a CSV file into the database."""
    from app.models import insert_company, insert_plan, get_company_by_ein
    from app.utils import normalize_company_name
    import csv
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
                company = get_company_by_ein(ein)
                if company:
                    insert_plan(company['id'], plan_name.strip(), plan_number, plan_type, year, ein, ack_id, year)
    except Exception as e:
        logger.error(f"Form 5500 import error: {e}")
        raise
    conn.commit()


def import_schedule_c_csv(filepath, year):
    """Import Schedule C data from a CSV file."""
    from app.schedule_c import parse_schedule_c
    conn = get_connection()
    plans = conn.execute("SELECT id, ein, plan_number FROM plans WHERE dataset_year=?", (year,)).fetchall()
    plan_map = {(p['ein'], p['plan_number']): p['id'] for p in plans if p['ein'] and p['plan_number']}
    parse_schedule_c(filepath, plan_map)


def check_and_update_datasets():
    """Legacy CLI trigger; now points to the interactive manager."""
    logger.info("Dataset update check triggered via CLI. Use interactive Dataset Manager for full control.")
    print("Use the interactive Dataset Manager to update datasets (option 5 in main menu).")