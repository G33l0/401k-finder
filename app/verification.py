import zipfile
import csv
import logging

logger = logging.getLogger(__name__)

def validate_zip_integrity(zip_path):
    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            bad = zf.testzip()
            if bad is not None:
                logger.error(f"Corrupt file in ZIP: {bad}")
                return False
        return True
    except Exception as e:
        logger.error(f"ZIP validation failed: {e}")
        return False

def validate_csv_columns(csv_path, required_columns):
    try:
        with open(csv_path, 'r', encoding='utf-8-sig') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            if not headers:
                return False
            missing = [col for col in required_columns if col not in headers]
            if missing:
                logger.warning(f"Missing columns in {csv_path}: {missing}")
                return False
        return True
    except Exception as e:
        logger.error(f"CSV validation error: {e}")
        return False