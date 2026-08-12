import json
import os
from pathlib import Path

DEFAULT_CONFIG_PATH = "config/config.json"

def load_config(path=None):
    if path is None:
        path = DEFAULT_CONFIG_PATH
    if not os.path.exists(path):
        return {
            "database_path": "data/401k_finder.db",
            "data_dir": "data",
            "raw_dir": "data/raw",
            "processed_dir": "data/processed",
            "cache_dir": "data/cache",
            "export_dir": "exports",
            "log_dir": "logs",
            "request_timeout": 30,
            "retry_count": 3,
            "update_check_interval_days": 30,
            "automatic_update": False,
            "online_verification": True,
            "color_enabled": True,
            "result_limit": 10,
            "confidence_high": 90,
            "confidence_medium": 70,
            "confidence_low": 50,
        }
    with open(path, 'r') as f:
        return json.load(f)

def ensure_dirs(config):
    for key in ['data_dir', 'raw_dir', 'processed_dir', 'cache_dir', 'export_dir', 'log_dir', 'backup_dir', 'metadata_dir']:
        Path(config.get(key, key)).mkdir(parents=True, exist_ok=True)