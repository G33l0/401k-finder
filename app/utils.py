import re
import urllib.parse
import shutil

def normalize_company_name(name):
    # ... (unchanged) ...
    if not name:
        return ""
    suffixes = [r'\bLLC\b', r'\bL\.L\.C\.?\b', r'\bINC\b', r'\bINC\.\b', r'\bCORPORATION\b', r'\bCORP\b',
                r'\bLTD\b', r'\bLIMITED\b', r'\bLP\b', r'\bL\.P\.?\b', r'\bLLP\b', r'\bL\.L\.P\.?\b', r'\bPLC\b']
    name = name.upper().strip()
    name = re.sub(r'[^\w\s]', '', name)
    for suffix in suffixes:
        name = re.sub(suffix, '', name, flags=re.IGNORECASE)
    return re.sub(r'\s+', ' ', name).strip()

def normalize_provider_name(name):
    """Light normalization for provider name matching."""
    if not name:
        return ""
    name = name.upper().strip()
    # Remove common business suffixes
    name = re.sub(r'\b(L\.?L\.?C\.?|INC\.?|CORP\.?|LTD\.?|LLP|PLC)\b', '', name)
    name = re.sub(r'[^\w\s]', '', name)
    return re.sub(r'\s+', ' ', name).strip()

def is_valid_url(url):
    try:
        result = urllib.parse.urlparse(url)
        return all([result.scheme in ['http', 'https'], result.netloc])
    except:
        return False

def safe_filename(name):
    return re.sub(r'[^\w\s-]', '', name).strip().replace(' ', '_')

def human_readable_size(size):
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size < 1024.0:
            return f"{size:.1f}{unit}"
        size /= 1024.0
    return f"{size:.1f}TB"

def get_free_disk_space(path='.'):
    """Return free space in bytes at the given path (Alpine compatible)."""
    try:
        stat = shutil.disk_usage(path)
        return stat.free
    except:
        return None