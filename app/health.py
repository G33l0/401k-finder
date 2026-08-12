import sys
import sqlite3
from app.config import load_config
from app.database import get_db_path

def run_health_check():
    print("Running health check...")
    checks = []
    # Python version
    checks.append(("Python version", sys.version_info >= (3, 8)))
    # SQLite tables
    try:
        conn = sqlite3.connect(get_db_path())
        conn.execute("SELECT 1")
        tables = ['provider_identities', 'provider_aliases', 'provider_name_history', 'provider_relationships']
        for t in tables:
            conn.execute(f"SELECT 1 FROM {t} LIMIT 0")
        checks.append(("Provider identity tables", True))
        conn.close()
    except Exception as e:
        checks.append(("Database integrity", False))
    # Data directories
    config = load_config()
    import os
    for d in ['data_dir', 'export_dir', 'log_dir']:
        path = config.get(d, d)
        checks.append((f"Directory {path}", os.path.isdir(path)))
    # Network (optional, does not affect overall health)
    try:
        import urllib.request
        urllib.request.urlopen("https://example.com", timeout=5)
        checks.append(("Network", True))
    except:
        checks.append(("Network (offline mode)", "WARN"))
    # Disk space
    from app.utils import get_free_disk_space
    free = get_free_disk_space()
    checks.append(("Disk space", free > 0 if free else "unknown"))
    # Overall – all boolean checks must pass, warnings are okay
    all_pass = all(v for _, v in checks if isinstance(v, bool))
    print("HEALTH CHECK RESULTS:")
    for name, status in checks:
        print(f"  {name}: {'PASS' if status is True else 'FAIL' if status is False else status}")
    if all_pass:
        print("SYSTEM HEALTH: PASS")
    else:
        print("SYSTEM HEALTH: WARNING")