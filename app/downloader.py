"""
Streaming downloader with progress, retry, resume, and SHA-256.
"""
import hashlib
import logging
import os
import time
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from app.config import load_config

logger = logging.getLogger(__name__)

DEFAULT_USER_AGENT = "401K-Provider-Finder/1.0 (+https://github.com/G33l0/401-finder)"


def _print_progress(downloaded, total, start_time, prefix=""):
    """Print simple progress bar."""
    if total and total > 0:
        pct = downloaded / total * 100
        bar_len = 30
        filled = int(bar_len * downloaded / total)
        bar = '█' * filled + '░' * (bar_len - filled)
        elapsed = max(time.time() - start_time, 0.001)
        speed = downloaded / elapsed
        eta = (total - downloaded) / speed if speed > 0 else 0
        print(f"\r{prefix} {downloaded}/{total} ({pct:.1f}%) |{bar}| {speed/1024:.1f} KB/s ETA {eta:.0f}s", end='')
    else:
        elapsed = max(time.time() - start_time, 0.001)
        speed = downloaded / elapsed
        print(f"\r{prefix} {downloaded} bytes (unknown total) {speed/1024:.1f} KB/s", end='')


def download_file(url, dest_path, expected_size=None, timeout=None, retries=None, resume=True):
    """
    Download a file with progress, retry, and optional resume.
    Saves to a temporary .part file, then renames atomically.
    """
    config = load_config()
    timeout = timeout or config.get('request_timeout', 30)
    retries = retries or config.get('retry_count', 3)
    user_agent = config.get('dol_user_agent', DEFAULT_USER_AGENT)

    part_path = str(dest_path) + '.part'
    downloaded = 0
    if resume and os.path.exists(part_path):
        downloaded = os.path.getsize(part_path)

    for attempt in range(retries):
        try:
            headers = {'User-Agent': user_agent}
            if resume and downloaded > 0:
                headers['Range'] = f'bytes={downloaded}-'
            req = Request(url, headers=headers)
            with urlopen(req, timeout=timeout) as resp:
                # Check if server ignored range and returned 200
                if resume and downloaded > 0 and resp.status != 206:
                    downloaded = 0  # restart from scratch
                    mode = 'wb'
                else:
                    mode = 'ab' if downloaded > 0 else 'wb'
                total = None
                content_length = resp.headers.get('Content-Length')
                if content_length:
                    total = downloaded + int(content_length)
                start = time.time()
                with open(part_path, mode) as f:
                    while True:
                        chunk = resp.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        _print_progress(downloaded, total, start, prefix="Downloading:")
                print()  # newline after progress
                # Validate expected size if provided
                if expected_size and os.path.getsize(part_path) != expected_size:
                    raise ValueError(f"Downloaded size {os.path.getsize(part_path)} != expected {expected_size}")
                # Atomic rename
                os.replace(part_path, dest_path)
                return True
        except Exception as e:
            logger.error(f"Download attempt {attempt+1} failed: {e}")
            if attempt < retries - 1:
                time.sleep(2 ** attempt)
            else:
                raise
    return False


def sha256_file(filepath):
    """Calculate SHA-256 hash of a file."""
    h = hashlib.sha256()
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(8192)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()