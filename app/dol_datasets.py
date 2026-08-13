"""
DOL Form 5500 Dataset Discovery Module - 2025 official static catalog.
"""
import json
import logging
import os
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
import socket

logger = logging.getLogger(__name__)

CACHE_FILE = "data/metadata/dol_datasets.json"
DEFAULT_USER_AGENT = "401K-Provider-Finder/1.0 (+https://github.com/G33l0/401-finder)"

# Official 2025 "All" dataset files with direct URLs
STATIC_CATALOG = {
    "2025": {
        "scope": "ALL",
        "files": [
            {
                "name": "F_5500_2025_All.zip",
                "url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_5500_2025_All.zip",
                "layout_url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_5500_2025_All_layout.txt",
                "file_type": "form_5500",
                "description": "Form 5500 All Filings 2025"
            },
            {
                "name": "F_5500_SF_2025_All.zip",
                "url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_5500_SF_2025_All.zip",
                "layout_url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_5500_SF_2025_All_layout.txt",
                "file_type": "form_5500_sf",
                "description": "Form 5500-SF All Filings 2025"
            },
            {
                "name": "F_SCH_A_2025_All.zip",
                "url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_SCH_A_2025_All.zip",
                "layout_url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_SCH_A_2025_All_layout.txt",
                "file_type": "schedule_a",
                "description": "Schedule A All 2025"
            },
            {
                "name": "F_SCH_C_2025_All.zip",
                "url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_SCH_C_2025_All.zip",
                "layout_url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_SCH_C_2025_All_layout.txt",
                "file_type": "schedule_c",
                "description": "Schedule C All 2025"
            },
            {
                "name": "F_SCH_D_2025_All.zip",
                "url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_SCH_D_2025_All.zip",
                "layout_url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_SCH_D_2025_All_layout.txt",
                "file_type": "schedule_d",
                "description": "Schedule D All 2025"
            },
            {
                "name": "F_SCH_H_2025_All.zip",
                "url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_SCH_H_2025_All.zip",
                "layout_url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_SCH_H_2025_All_layout.txt",
                "file_type": "schedule_h",
                "description": "Schedule H All 2025"
            },
            {
                "name": "F_SCH_I_2025_All.zip",
                "url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_SCH_I_2025_All.zip",
                "layout_url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_SCH_I_2025_All_layout.txt",
                "file_type": "schedule_i",
                "description": "Schedule I All 2025"
            },
            {
                "name": "F_SCH_R_2025_All.zip",
                "url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_SCH_R_2025_All.zip",
                "layout_url": "https://askebsa.dol.gov/FOIA%20Files/2025/All/F_SCH_R_2025_All_layout.txt",
                "file_type": "schedule_r",
                "description": "Schedule R All 2025"
            }
        ]
    }
}

def discover_datasets(force_refresh=False):
    """Return dataset metadata. Always uses static catalog for 2025 (no live parsing)."""
    # If cache exists, return it (unless forced)
    if os.path.exists(CACHE_FILE) and not force_refresh:
        try:
            with open(CACHE_FILE, 'r') as f:
                cached = json.load(f)
                if cached.get('datasets'):
                    return cached
        except Exception:
            pass

    metadata = {
        'discovered_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
        'latest_year': '2025',
        'years': ['2025'],
        'datasets': {
            '2025': STATIC_CATALOG['2025']['files']
        },
        'source': 'static_official_2025'
    }
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(metadata, f, indent=2)
    return metadata

def get_dataset_links(year=None, force_refresh=False):
    """Return flat list of dataset file dicts for a given year."""
    metadata = discover_datasets(force_refresh)
    links = []
    for y, files in metadata['datasets'].items():
        if year is not None and int(y) != year:
            continue
        for f in files:
            f['year'] = int(y)
            links.append(f)
    return links

def run_dol_diagnostics():
    """Simple connectivity test to DOL direct URLs."""
    result = {
        'dns': False,
        'tls': False,
        'http': False,
        'page': False,
        'discovery': False,
        'latest_year': None,
        'file_count': 0,
        'cache': os.path.exists(CACHE_FILE),
        'error': None
    }
    # Test one URL
    test_url = STATIC_CATALOG['2025']['files'][0]['url']
    host = urlparse(test_url).hostname
    try:
        socket.getaddrinfo(host, 443)
        result['dns'] = True
    except Exception as e:
        result['error'] = f"DNS failed: {e}"
        return result
    try:
        req = Request(test_url, headers={'User-Agent': DEFAULT_USER_AGENT})
        with urlopen(req, timeout=15) as resp:
            result['tls'] = True
            result['http'] = True
            result['page'] = True
            result['discovery'] = True
            result['latest_year'] = 2025
            result['file_count'] = len(STATIC_CATALOG['2025']['files'])
    except Exception as e:
        result['error'] = str(e)
    return result