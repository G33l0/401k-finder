"""
DOL Form 5500 Dataset Discovery Module.

This module retrieves the official DOL dataset catalog page,
parses the HTML to discover actual dataset download links,
and returns a structured catalog. It never fabricates URLs.
"""
import json
import logging
import os
import re
import socket
import time
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlparse
from app.config import load_config

logger = logging.getLogger(__name__)

CACHE_FILE = "data/metadata/dol_datasets.json"
DEFAULT_USER_AGENT = "401K-Provider-Finder/1.0 (+https://github.com/G33l0/401-finder)"


class DOLDatasetHTMLParser(HTMLParser):
    """Parses the DOL dataset page and extracts all dataset links."""

    def __init__(self, base_url):
        super().__init__()
        self.base_url = base_url
        self.links = []           # list of dicts: {year, name, url, description, file_type}
        self._current_year = None
        self._in_heading = False
        self._in_link = False
        self._current_href = None
        self._link_text = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag in ('h1', 'h2', 'h3', 'h4', 'td'):
            # Look for year in headings/table cells
            text = ''
            # Can't capture text easily here; use data later
            pass
        if tag == 'a':
            self._in_link = True
            self._current_href = attrs.get('href', '')
            self._link_text = []

    def handle_data(self, data):
        if self._in_link:
            self._link_text.append(data.strip())

    def handle_endtag(self, tag):
        if tag == 'a' and self._in_link:
            href = self._current_href
            text = ' '.join(self._link_text).strip()
            self._in_link = False
            if not href:
                return
            # Only consider actual download links (zip, csv, or known DOL patterns)
            lower_href = href.lower()
            if not (lower_href.endswith('.zip') or lower_href.endswith('.csv') or 'dataset' in lower_href):
                return
            absolute_url = urljoin(self.base_url, href)
            filename = href.split('/')[-1]
            # Extract year from URL or text
            year = None
            m = re.search(r'(\d{4})', href)
            if m:
                year = int(m.group(1))
            else:
                m = re.search(r'(\d{4})', text)
                if m:
                    year = int(m.group(1))
            if year is None or year < 1990 or year > 2100:
                # Try from filename
                m = re.search(r'(\d{4})', filename)
                if m:
                    year = int(m.group(1))
            if year is None:
                year = self._current_year  # might be None, skip if unknown
            if year is None:
                return
            # Determine type
            file_type = self._classify_dataset(text, filename)
            self.links.append({
                'year': year,
                'name': filename,
                'url': absolute_url,
                'description': text or filename,
                'file_type': file_type
            })

    def _classify_dataset(self, text, filename):
        lower = (text + ' ' + filename).lower()
        if 'latest' in lower:
            return 'latest'
        if 'all' in lower:
            return 'all'
        if 'schedule c' in lower or 'sch-c' in lower:
            return 'schedule_c'
        if 'schedule a' in lower or 'sch-a' in lower:
            return 'schedule_a'
        if 'schedule d' in lower or 'sch-d' in lower:
            return 'schedule_d'
        if 'schedule g' in lower or 'sch-g' in lower:
            return 'schedule_g'
        if 'schedule h' in lower or 'sch-h' in lower:
            return 'schedule_h'
        if 'schedule i' in lower or 'sch-i' in lower:
            return 'schedule_i'
        if 'schedule r' in lower or 'sch-r' in lower:
            return 'schedule_r'
        if 'form 5500-sf' in lower or '5500-sf' in lower:
            return 'form_5500_sf'
        if 'form 5500' in lower or '5500' in lower:
            return 'form_5500'
        return 'other'


def fetch_dol_page(url, timeout=30, user_agent=None):
    """Fetch HTML content of DOL page with retries."""
    config = load_config()
    user_agent = user_agent or config.get('dol_user_agent', DEFAULT_USER_AGENT)
    retries = config.get('retry_count', 3)
    backoff = 1
    last_error = None
    for attempt in range(retries):
        try:
            req = Request(url, headers={'User-Agent': user_agent})
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode('utf-8', errors='ignore')
        except HTTPError as e:
            last_error = f"HTTP {e.code}: {e.reason}"
            logger.error(f"HTTP error on attempt {attempt+1}: {last_error}")
            if e.code in (403, 404):
                break
        except URLError as e:
            last_error = f"Connection error: {e.reason}"
            logger.error(f"Connection error on attempt {attempt+1}: {last_error}")
        except Exception as e:
            last_error = f"Unexpected error: {e}"
            logger.error(f"Unexpected error on attempt {attempt+1}: {last_error}")
        time.sleep(backoff)
        backoff *= 2
    raise ConnectionError(f"Failed to fetch DOL page: {last_error}")


def discover_datasets(force_refresh=False):
    """
    Discover available datasets from DOL page.
    Returns a dict with:
        discovered_at, latest_year, datasets: {year: [ {name, url, description, file_type}, ... ]}
    Falls back to cache if offline.
    """
    cache = _load_cache()
    if cache and not force_refresh:
        logger.info("Using cached DOL dataset metadata.")
        return cache

    config = load_config()
    url = config.get('dol_index_url')
    if not url:
        raise ValueError("DOL index URL not configured")

    try:
        html = fetch_dol_page(url)
        parser = DOLDatasetHTMLParser(url)
        parser.feed(html)

        # Build structured catalog by year
        catalog = {}
        for link in parser.links:
            year = link['year']
            catalog.setdefault(str(year), []).append(link)

        if not catalog:
            raise ValueError("No dataset links found on DOL page")

        latest_year = str(max(int(y) for y in catalog.keys()))
        metadata = {
            'discovered_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'latest_year': latest_year,
            'datasets': catalog,
            'years': sorted(catalog.keys(), key=int)
        }
        _save_cache(metadata)
        return metadata
    except Exception as e:
        logger.error(f"Dataset discovery failed: {e}")
        if cache:
            logger.warning("Falling back to cached metadata.")
            return cache
        raise


def get_dataset_links(year=None, force_refresh=False):
    """Return a flat list of dataset links, optionally filtered by year."""
    metadata = discover_datasets(force_refresh)
    links = []
    for y, files in metadata['datasets'].items():
        if year is not None and int(y) != year:
            continue
        for f in files:
            f['year'] = int(y)
            links.append(f)
    return links


def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            pass
    return None


def _save_cache(data):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, indent=2)