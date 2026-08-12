import urllib.request
import hashlib
import os
import logging
from app.config import load_config

logger = logging.getLogger(__name__)

def download_file(url, dest_path, expected_size=None, timeout=None, retries=None):
    config = load_config()
    timeout = timeout or config.get('request_timeout', 30)
    retries = retries or config.get('retry_count', 3)
    for attempt in range(retries):
        try:
            logger.info(f"Downloading {url} (attempt {attempt+1})")
            req = urllib.request.Request(url, headers={'User-Agent': '401k-finder/1.0'})
            with urllib.request.urlopen(req, timeout=timeout) as response:
                with open(dest_path, 'wb') as f:
                    while True:
                        chunk = response.read(8192)
                        if not chunk:
                            break
                        f.write(chunk)
            if expected_size and os.path.getsize(dest_path) != expected_size:
                raise ValueError("Downloaded size mismatch")
            return True
        except Exception as e:
            logger.error(f"Download attempt failed: {e}")
            if attempt == retries - 1:
                raise
    return False

def get_remote_file_size(url, timeout=None):
    config = load_config()
    timeout = timeout or config.get('request_timeout', 30)
    try:
        req = urllib.request.Request(url, method='HEAD', headers={'User-Agent': '401k-finder/1.0'})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            length = resp.headers.get('Content-Length')
            if length:
                return int(length)
    except:
        pass
    return None