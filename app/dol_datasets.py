import json
import logging
import os
import re
import socket
import time
from pathlib import Path
from html.parser import HTMLParser
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from app.config import load_config
from app.utils import human_readable_size

logger = logging.getLogger(__name__)
CACHE_FILE = "data/metadata/dol_datasets.json"
DEFAULT_USER_AGENT = "401k-Finder/1.0 (compatible; +https://github.com/401k-finder)"


class DOLDatasetHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.datasets = {}
        self._current_year = None
        self._capture = False
        self._in_link = False
        self._current_url = ''
        self._current_filename = ''

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            href = dict(attrs).get('href', '')
            self._in_link = True
            match = re.search(r'(\d{4})', href)
            if match:
                year = int(match.group(1))
                if 1999 <= year <= 2099:
                    self._current_year = year
                    self._capture = True
                    if href.startswith('http'):
                        self._current_url = href
                    else:
                        self._current_url = 'https://www.dol.gov' + href
                    self._current_filename = href.split('/')[-1]

    def handle_data(self, data):
        if self._capture and self._in_link:
            size_match = re.search(r'\((\d+\.?\d*)\s*(MB|GB|KB)\)', data, re.IGNORECASE)
            if size_match:
                size = float(size_match.group(1))
                unit = size_match.group(2).upper()
                if unit == 'KB':
                    size *= 1024
                elif unit == 'MB':
                    size *= 1024 * 1024
                elif unit == 'GB':
                    size *= 1024 * 1024 * 1024
                else:
                    size = None
                if self._current_year not in self.datasets:
                    self.datasets[self._current_year] = []
                self.datasets[self._current_year].append((self._current_filename, self._current_url, size))
                self._capture = False

    def handle_endtag(self, tag):
        if tag == 'a':
            self._in_link = False
            self._capture = False


def _fetch_page(url, timeout=30):
    config = load_config()
    user_agent = config.get('dol_user_agent', DEFAULT_USER_AGENT)
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
    raise ConnectionError(f"Failed to fetch {url}: {last_error}")


def _load_cache():
    if os.path.exists(CACHE_FILE):
        try:
            with open(CACHE_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return None


def _save_cache(data):
    os.makedirs(os.path.dirname(CACHE_FILE), exist_ok=True)
    with open(CACHE_FILE, 'w') as f:
        json.dump(data, f, indent=2)


def discover_datasets(force_refresh=False):
    """Discover available datasets from DOL page, fallback to cache if offline."""
    cache = _load_cache()
    if cache and not force_refresh:
        logger.info("Using cached DOL dataset metadata.")
        return cache
    config = load_config()
    url = config.get('dol_index_url')
    if not url:
        raise ValueError("DOL index URL not configured")
    try:
        html = _fetch_page(url)
        parser = DOLDatasetHTMLParser()
        parser.feed(html)
        catalog = {}
        for year, files in parser.datasets.items():
            catalog[str(year)] = []
            for fname, url, size in files:
                catalog[str(year)].append({
                    'name': fname,
                    'url': url,
                    'compressed_size': size,
                    'type': 'unknown'
                })
        metadata = {
            'discovered_at': time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime()),
            'latest_year': str(max(parser.datasets.keys())) if parser.datasets else None,
            'years': sorted(catalog.keys()),
            'datasets': catalog
        }
        _save_cache(metadata)
        return metadata
    except Exception as e:
        logger.error(f"Dataset discovery failed: {e}")
        if cache:
            logger.warning("Falling back to cached metadata.")
            return cache
        raise


def run_dol_diagnostics():
    """Diagnostic test for DOL connectivity."""
    result = {
        'dns': False, 'tls': False, 'http': False,
        'page': False, 'discovery': False,
        'latest_year': None, 'file_count': 0,
        'cache': os.path.exists(CACHE_FILE),
        'error': None
    }
    config = load_config()
    url = config.get('dol_index_url')
    user_agent = config.get('dol_user_agent', DEFAULT_USER_AGENT)

    # DNS
    import urllib.parse
    host = urllib.parse.urlparse(url).hostname
    try:
        socket.getaddrinfo(host, 443)
        result['dns'] = True
    except Exception as e:
        result['error'] = f"DNS failed: {e}"
        return result

    # HTTP/TLS
    try:
        req = Request(url, headers={'User-Agent': user_agent})
        with urlopen(req, timeout=15) as resp:
            result['tls'] = True
            result['http'] = True
            html = resp.read().decode('utf-8', errors='ignore')
            result['page'] = True
    except HTTPError as e:
        result['tls'] = True
        result['http'] = False
        result['error'] = f"HTTP {e.code}: {e.reason}"
        return result
    except URLError as e:
        result['error'] = f"Connection: {e.reason}"
        if 'certificate' in str(e).lower():
            result['tls'] = False
        return result
    except Exception as e:
        result['error'] = str(e)
        return result

    # Parsing
    try:
        parser = DOLDatasetHTMLParser()
        parser.feed(html)
        if parser.datasets:
            result['discovery'] = True
            result['latest_year'] = max(parser.datasets.keys())
            result['file_count'] = sum(len(v) for v in parser.datasets.values())
        else:
            result['discovery'] = False
            result['error'] = "No dataset links found"
    except Exception as e:
        result['discovery'] = False
        result['error'] = f"Parsing error: {e}"

    return result