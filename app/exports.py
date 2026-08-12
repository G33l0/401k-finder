import json
import csv
import os
from pathlib import Path
from app.config import load_config

def export_result(result, format='json'):
    config = load_config()
    export_dir = Path(config['export_dir'])
    export_dir.mkdir(exist_ok=True)
    base_name = f"search_{result['company'].replace(' ','_')}_{result.get('year','')}"
    if format == 'json':
        filepath = export_dir / f"{base_name}.json"
        with open(filepath, 'w') as f:
            json.dump(result, f, indent=2)
    elif format == 'csv':
        filepath = export_dir / f"{base_name}.csv"
        with open(filepath, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['key', 'value'])
            for k, v in result.items():
                writer.writerow([k, v])
    elif format == 'txt':
        filepath = export_dir / f"{base_name}.txt"
        with open(filepath, 'w') as f:
            for k, v in result.items():
                f.write(f"{k}: {v}\n")
    print(f"Exported to {filepath}")