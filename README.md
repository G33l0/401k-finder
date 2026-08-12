# 401 Finder

> Search 401(k) plans, providers, EINs, and historical retirement-plan information from public Form 5500 data.

**401 Finder** is a lightweight retirement-plan research tool designed to identify the 401(k) provider associated with a company and a specific plan year.

## ✨ Features

- 🔎 Search by company name
- 🆔 Identify employer EINs
- 📋 Find 401(k) plan information
- 🏦 Identify retirement-plan service providers
- 📅 Search by specific plan year
- 🕘 Explore historical provider information
- 🔄 Resolve historical provider names to current identities
- 💾 Local Form 5500 dataset caching
- ⚡ Fast offline searches using SQLite
- 📦 Selective dataset installation
- 📊 Provider confidence and evidence
- 🔗 Official provider website and login links
- 🐧 Alpine Linux / iSH support

## 🧠 How It Works

```text
Company Name
     │
     ▼
Company / EIN Matching
     │
     ▼
Form 5500 Dataset
     │
     ▼
401(k) Plan Identification
     │
     ▼
Schedule C / Provider Analysis
     │
     ▼
Provider Identity Resolution
     │
     ▼
Current + Historical Provider
     │
     ▼
Evidence & Confidence

📦 Data

401 Finder uses the U.S. Department of Labor Form 5500 datasets.

Official source:

https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/public-disclosure/foia/form-5500-datasets

Datasets are cached and processed locally so normal searches do not repeatedly query the DOL website.

🏦 Provider Identity

Provider names can change over time.

Example:

Historical Filing
Great-West Life & Annuity
        │
        ▼
Provider Identity
Empower

401 Finder preserves the exact provider name reported in the historical filing while separately maintaining the normalized/current provider identity.

This allows the system to distinguish between:
	•	Historical filing name
	•	Current provider name
	•	Legal entity
	•	Brand name
	•	Former name
	•	Provider aliases
	•	Provider transitions

📅 Historical Research

Search by company and plan year:

Company: Broulim's Supermarkets
Year: 2025

Historical datasets can be installed when needed instead of downloading every available year during initial setup.

💾 Dataset Installer

The first-run installer provides:

1. Essential
2. Standard
3. Full
4. Custom
5. Offline

The installer dynamically calculates:
	•	Download size
	•	Extracted size
	•	Database size
	•	Temporary processing space
	•	Required free storage

Dataset sizes are discovered from the actual DOL files rather than hardcoded.

🐧 Alpine Linux / iSH

Designed for lightweight environments:

Alpine Linux
iSH
Python 3
SQLite

No Docker or systemd is required.

🚀 Installation

git clone https://github.com/g33l0/401-finder.git
cd 401-finder
pip install -r requirements.txt
python main.py

🔍 Examples

python main.py --company "G33l0's Supermarkets" --year 2025

python main.py --company "G33l0's Supermarkets" --history

python main.py --provider "xyz"

python main.py --health

python main.py --self-test

🧪 Testing

Run the test suite:

python -m unittest discover

Run the application self-test:

python main.py --self-test

Run the health check:

python main.py --health

🔐 Privacy & Security

401 Finder is designed primarily around publicly available retirement-plan information.

The application should never request or store:
	•	Social Security numbers
	•	401(k) account passwords
	•	Provider login credentials
	•	Banking credentials
	•	Authentication tokens

Provider login links point users to the provider’s official website.

⚠️ Disclaimer

401 Finder is a research and data-discovery tool.

Form 5500 information may be incomplete, delayed, amended, or historical. Provider information should be verified against the underlying filing and official provider sources before being used for financial, legal, or administrative decisions.

🛠️ Project Status

Development

Current development focuses on:
	•	Form 5500 data processing
	•	Company and EIN matching
	•	401(k) plan discovery
	•	Provider identification
	•	Historical provider tracking
	•	Provider identity resolution
	•	Local/offline search
	•	Dataset management
	•	Evidence and confidence scoring
	•	Official provider links
	•	Alpine Linux / iSH compatibility

📄 License

See LICENSE for license information.

👤 Author

g33l0

GitHub: https://github.com/g33l0

⸻

401 Finder

Public Form 5500 data → searchable retirement-plan intelligence.

