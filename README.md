# 401K Finder Pro

Find retirement plans — and the firms that hold and administer them — from the
U.S. Department of Labor's public Form 5500 filings.

Every U.S. employer-sponsored retirement plan covered by ERISA files a Form 5500
each year, and EBSA publishes the whole dataset. Those files answer a question
that is otherwise hard to answer: *who actually holds this 401(k), and who runs
it?* They also make it awkward — the data arrives as two dozen separate CSV
files per year, joined by an acknowledgement ID, with the provider information
scattered across five different schedules.

This application downloads those files, joins them correctly, and makes them
searchable. It runs entirely on your machine and cites the exact filing field
behind every answer.

```
$ 401k-finder search "acme manufacturing" --feature 401K

ACME 401(K) PROFIT SHARING PLAN
  Sponsor: ACME MANUFACTURING INC  |  EIN 010000000-001  |  Springfield, IL
  DEFINED_CONTRIBUTION [401K, PARTICIPANT_DIRECTED, PROFIT_SHARING]  |  120 participants  |  $5.0M
    Recordkeeper               Fidelity Investments      [C-1-2 2023] (15, 37, 64, 50, 38)
    Trustee                    Matrix Trust / Broadridge [H 2023]
    Investment Manager         Fidelity Investments      [D-1 2023]
    Accountant                 CliftonLarsonAllen        [H 2023]
```

---

## What it covers

Form 5500 covers far more than 401(k) plans, and so does this tool. Plans are
classified from the plan characteristics codes filed on line 8a:

| Account type | How it is identified |
|---|---|
| 401(k) | code `2J`, or the Schedule R / 5500-SF `401K_PLAN_IND` box |
| 403(b) | codes `2L` (annuity contracts) and `2M` (custodial accounts) |
| 457(b) | plan name — 457 plans have no characteristics code of their own |
| SEP and SIMPLE | code `2N` (Code section 408 accounts and annuities) |
| Profit sharing | codes `2E`, `2A` |
| Money purchase / target benefit | codes `2C`, `2B` |
| ESOP | codes `2O`, `2P`, `2Q`, and Schedule R's ESOP boxes |
| Stock bonus | code `2I` |
| Defined benefit pension | codes `1A`–`1I` |
| Cash balance | code `1C` |
| Pooled employer plans (PEP) | code `2W`, and Schedule MEP |
| Multiemployer / multiple-employer | plan entity code, codes `2U`–`2X` |

Welfare benefit plans (health, dental, life) are parsed too, but filtered out of
search results by default.

**What Form 5500 does not cover.** Only plans subject to Title I of ERISA file,
so some retirement accounts are largely or entirely absent no matter how well
the tool works:

- **Governmental 457(b) plans** are exempt, so a search for 457 plans returns
  almost nothing. The handful that appear are non-governmental arrangements.
- **Church plans** that have not elected ERISA coverage.
- **Solo 401(k) and one-participant plans** file Form 5500-EZ with the IRS,
  which is not part of this public dataset.
- **IRAs, and SEP/SIMPLE plans using individual IRAs**, generally have no
  filing obligation — code 2N appears only where a pension plan is funded
  through Code section 408 accounts, which is rare.

## Where the provider answers come from

No single field says "this is the recordkeeper". The answer is assembled from
several schedules, each with a different reliability, and the tool records which
one it used:

| Source | What it names | Confidence |
|---|---|---|
| **Schedule C Part 1 Item 2** | Service providers with service codes and what the plan paid them. Codes distinguish recordkeeper (15) from trustee (21), custodian (19), investment manager (28), auditor (10). | High |
| **Schedule H** | Trustee or custodian, fiduciary trust, and the auditing accountant, for plans with 100+ participants. | High |
| **Schedule I** | Trustee or custodian, for smaller plans. | High |
| **Form 5500-SF** | Trustee or custodian, self-contained — the most productive source for small-employer plans. | High |
| **Schedule A** | The insurance carrier holding annuity or insurance contracts. Often the only asset holder named for 403(b) and small plans. | High |
| **Schedule D Part 1** | Master trusts, collective trusts and pooled separate accounts holding plan assets. | High |
| **Schedule A Part 1** | Brokers receiving commissions. | High |
| **Form 5500 / SF** | Plan administrator, form preparer. | Medium / low |

Every one of these writes an evidence record naming the dataset, file, row,
field and acknowledgement ID it came from. `401k-finder plan <ein> --evidence`
prints the whole trail.

---

## Installing

### Windows

Download the installer from the releases page and run it. No Python required.
It installs both the desktop application and `401k-finder.exe`, the same
command line described below, in the install folder.

To build it yourself, see **[docs/DEPLOY.md](docs/DEPLOY.md)** — a step-by-step
guide that assumes no prior experience, and covers where to put your icon and
logo. [docs/WINDOWS_APPLICATION.md](docs/WINDOWS_APPLICATION.md) is the
reference on how the packaging works.

### From source (any platform)

Requires Python 3.11, 3.12 or 3.13.

```bash
git clone https://github.com/g33l0/401k-finder.git
cd 401k-finder

python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt

401k-finder init
```

---

## Getting data

The application starts empty. Load a form year from DOL:

```bash
401k-finder sync --year 2023
```

This downloads the core datasets — the two main forms plus Schedules A, C Part 1
Item 2, D Part 1, H, I, R, DCG and MEP — which carry every provider field.
Expect a few gigabytes and 15–60 minutes depending on your connection.

For scale: the 2023 Form 5500 dataset alone is 231,725 filings covering 223,847
plans, and imports in about three minutes on a modest machine. Adding the
5500-SF and the schedules multiplies that several times over.

```bash
401k-finder sync --year 2023 --all-datasets   # every published dataset
401k-finder sync --year 2022 --year 2023      # several years
401k-finder sync --year 2023 --release All    # every filing, not just the latest per plan
```

Syncs are resumable. Interrupt one and re-run it; completed datasets are
skipped and a partial download continues where it stopped.

Already have the files? Import them from disk:

```bash
401k-finder import /path/to/dol/csvs --year 2023
```

Check what is loaded at any time:

```bash
401k-finder status
```

### Latest vs All

DOL publishes each year twice. **Latest** has one row per plan year, with
superseded filings removed — this is what you want. **All** includes every
filing received, including amendments and duplicates, and is useful only if you
are studying filing behaviour itself.

---

## Using it

### Desktop application

```bash
401k-finder-gui
```

Three tabs: **Find plans** (search, results, and a detail panel with the
provider list and full evidence), **Providers** (which firms hold the most
plans, and drill into their book), and **Data** (download years, import local
files, see what is loaded).

### Command line

```bash
# Text search
401k-finder search "acme manufacturing"

# Straight to a plan by EIN, or EIN and plan number
401k-finder search 12-3456789
401k-finder plan 12-3456789/001 --filings

# Every 401(k) plan in Texas with 500+ participants served by Fidelity
401k-finder search --state TX --feature 401K --min-participants 500 --provider Fidelity

# Every plan where a firm is specifically the recordkeeper
401k-finder search --provider Empower --role RECORDKEEPER

# Which recordkeepers hold the most plans
401k-finder providers --role RECORDKEEPER

# Full evidence report for one plan
401k-finder plan 12-3456789/001 --evidence

# Export
401k-finder search --state CA --feature 403B --csv california-403b.csv
```

`401k-finder <command> --help` for the full set of options.

---

## How the data fits together

The single most important fact about these files: **schedule datasets contain no
plan identity.** A Schedule H row is an `ACK_ID` and a hundred dollar amounts —
no employer name, no EIN, no plan name. Schedules are joined to filings by
`ACK_ID`, and only the filing datasets say which plan a filing belongs to.

So the import runs in two passes:

```
Pass 1   F_5500, F_5500_SF, F_SCH_DCG
         → creates plans (keyed by sponsor EIN + plan number)
         → creates filings (keyed by ACK_ID)

Pass 2   F_SCH_A, F_SCH_C_PART1_ITEM2, F_SCH_D_PART1, F_SCH_H, F_SCH_I, ...
         → joined to pass-1 filings by ACK_ID
         → provider names extracted and attributed to the plan
```

Financial totals need the same care. Form 5500 itself carries no asset figures —
for a large plan they are on Schedule H, for a small one on Schedule I — so
filings are enriched from those schedules as they import, and plan-level totals
are rolled up at the end.

If you import schedules without their filing datasets, the schedule rows are
kept but reported as unmatched; import the matching `F_5500` / `F_5500_SF` for
the same year and re-run to attach them.

### Layouts are data, not assumptions

DOL publishes a machine-readable layout file next to every dataset:

```
FIELD_POSITION,FIELD_NAME,TYPE,SIZE (only for text fields)
===========================================
1,ACK_ID,TEXT,30
2,FORM_PLAN_YEAR_BEGIN_DATE,TEXT,10
```

All 448 of them — 28 datasets across 17 form years, 2009 to 2025 — are vendored
in [`app/dol/layouts/data/`](app/dol/layouts/data). Parsing, validation and
provider extraction all read from these rather than from hard-coded field lists,
so the application works offline and a layout change is a data change.

Check the vendored copies against what DOL publishes today:

```bash
python -m scripts.refresh_layouts --check     # report drift
python -m scripts.refresh_layouts             # update
```

---

## Layout of the project

```
app/
  cli.py                 Command-line interface
  main.py                Desktop application entry point
  core/                  Config, logging, exceptions, DOL code tables
  dol/                   Everything about the DOL files
    layouts/data/        The 448 vendored layout files, per year
    catalog.py           Dataset URLs and per-year availability
    downloader.py        Streaming download with resume
    archive.py           ZIP extraction with path-traversal checks
    csv_reader.py        Encoding detection, tolerant row reading
    filing_parser.py     Filing row → normalized values, plan classification
    provider_extractor.py Field-to-role rules for every provider source
    importer.py          The two-pass pipeline
    validator.py         Files checked against their published layouts
    schedules/           What each dataset's columns mean
  database/              Models, engine, sessions, versioned schema
  providers/             Name normalisation, brand table, fuzzy matching
  search/                Query objects and the FTS5-backed search engine
  evidence/              Evidence trail assembly
  services/              Sync, export, statistics
  ui/                    PySide6 window, widgets and background workers
database/
  migrations/            Schema snapshots (migrations live in code)
  seeds/                 Extra provider brands you can add without editing code
docs/                    Deployment walkthrough and packaging reference
installer/               PyInstaller spec and Inno Setup script
scripts/                 Layout refresh, test-data generation
tests/                   Test suite
```

---

## Development

```bash
pip install -r requirements.txt -r requirements-dev.txt

python -m scripts.make_test_data --year 2023 --plans 48   # synthetic DOL files
pytest -q
ruff check app tests scripts
```

The test suite runs without network access and without downloading anything. It
generates synthetic CSVs that use the **real** published column set for each
dataset, so structural bugs surface exactly as they would against live data.

The layout tests are worth knowing about: they assert that every vendored layout
has `ACK_ID`, that field positions are contiguous, that the identity fields the
parser depends on exist in every year it claims to support, and that every
provider-extraction rule points at a field that actually exists. A rule aimed at
a misspelled field would otherwise fail silently and simply never find anyone.

---

## Notes and limits

- **Filing lag.** Form 5500 is due roughly seven months after the plan year ends,
  and extensions are common. The most recent complete year is usually two years
  back. Partial years are published as filings arrive.
- **Provider names are what was filed.** Schedule C truncates the name field to
  35 characters, so a firm appears under many spellings. Names are grouped by a
  normalized key and well-known firms are mapped to a canonical name; unknown
  firms keep their filed spelling exactly. Nothing is merged automatically on a
  fuzzy match — that judgement is left to you, via
  `app/providers/matcher.py` and the seed file in `database/seeds/`.
- **Not every plan names a provider.** A small plan filing a 5500-SF with no
  trustee named will show none. That is the filing, not a bug.
- **Not an ERISA compliance tool.** This reads public filings and reports what
  they say. It does not evaluate fees, fiduciary conduct or plan health, and it
  is not advice.
- **Individual participants never appear.** Form 5500 reports plan-level data
  only — counts and totals, never people. There is no personal data here.

## Source and licence of the data

All data comes from the U.S. Department of Labor, Employee Benefits Security
Administration:

<https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/public-disclosure/foia/form-5500-datasets>

The filings are public records released under FOIA. Original filing images can
be retrieved from EBSA's [EFAST filing search](https://www.efast.dol.gov/5500search/)
using the sponsor EIN and plan number this application shows.
