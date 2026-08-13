```markdown
# 401K Provider Finder

A terminal‑based research tool that helps identify the 401(k) retirement plan recordkeeper/provider for a U.S. company using public Form 5500 data from the U.S. Department of Labor (DOL).

Built for Alpine Linux / iSH on iPhone/iPad, but works on any Python 3.8+ environment.

## Features

- Interactive CLI with first‑run dataset installer
- Dynamic discovery of official DOL Form 5500 datasets (with static fallback)
- Essential / Standard / Full / Custom dataset packages
- Local SQLite database for fast offline searches
- Company name → EIN → Plan → Service Provider pipeline
- Provider identity resolution (historical names → current brands, e.g., Great‑West → Empower)
- Provider directory with verified login URLs
- Historical provider tracking and timelines
- Confidence scoring and evidence display
- Export results to JSON / CSV / TXT
- Health checks and network diagnostics
- Offline mode after dataset installation

## Requirements

- Python 3.8 or higher
- SQLite (built‑in)
- No external dependencies except `rich` (for terminal UI)

## Installation

```bash
# On Alpine/iSH:
apk add python3 py3-pip
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# On Windows:
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

First Run

Run the application:

```bash
python main.py
```

If no dataset is installed, the setup wizard appears:

1. Essential – smallest, for basic 401(k) provider lookups (Form 5500 + Schedule C)
2. Standard – recommended, includes additional schedules
3. Full – complete latest dataset
4. Custom – choose individual files
5. Offline / Skip – continue without DOL data

The installer automatically detects the latest dataset year (currently 2025) and displays real file sizes.

CLI Commands

```bash
# Search for a company's 401(k) provider
python main.py --company "Broulim's Supermarkets" --year 2025

# Get JSON output
python main.py --company "Broulim's Supermarkets" --year 2025 --json

# Find EIN for a company
python main.py --company "Broulim's Supermarkets" --ein

# Show provider history
python main.py --company "Broulim's Supermarkets" --history

# Search provider directory
python main.py --provider "Empower"

# Test DOL connectivity
python main.py --test-dol

# Discover available datasets
python main.py --discover-datasets

# Download a dataset for a specific year
python main.py --download-dataset 2025

# Build database from downloaded dataset
python main.py --build-database 2025

# Verify dataset integrity
python main.py --verify-dataset 2025

# Import a local dataset ZIP
python main.py --import-dataset /path/to/dataset.zip --year 2025

# Run self‑test
python main.py --self-test

# Check system health
python main.py --health
```

Dataset Manager

From the interactive main menu, choose 5. Dataset Manager to:

· Install/Update dataset
· Download historical datasets
· Show installed datasets
· Import local files (offline)
· Backup/validate

Data Storage

· Raw downloads: data/raw/<year>/
· Extracted files: data/raw/<year>/extracted/
· SQLite database: data/401k_finder.db
· Metadata: data/metadata/

The data/metadata/dol_datasets.json file caches discovered dataset links and status.

Provider Identity

The tool preserves historical filing names and maps them to current providers using an alias system. For example:

· Historical name (2018 filing): Great‑West Life & Annuity
· Canonical identity: Empower
· Current name: Empower Retirement

This mapping is stored in provider_aliases, provider_name_history, and provider_relationships tables and can be managed via Provider Directory menu.

Offline Mode

Once datasets are installed, all searches run entirely offline. No network calls are made during normal company searches.

If DOL is unreachable during setup, the app offers a retry / offline option and falls back to cached metadata.

Troubleshooting

· “Unable to contact DOL dataset service” – Run python main.py --test-dol to see if it’s a DNS, TLS, HTTP, or parsing issue.
· “Dataset file not found” – Use --download-dataset or import a local ZIP.
· “Insufficient storage” – Choose Essential or Custom package.
· Windows terminal issues – Use Windows Terminal or enable ANSI colors.

Testing

Run the self‑test suite:

```bash
python main.py --self-test
```

This checks database connectivity, company matching, EIN discovery, plan detection, provider classification, identity resolution, URL validation, and exports.

Disclaimer

This tool uses only publicly available data from the U.S. Department of Labor. It does not access private retirement accounts, and it never collects SSNs or login credentials. All provider login links are manually verified and stored locally.

License

MIT License – see LICENSE file for details.

```
```