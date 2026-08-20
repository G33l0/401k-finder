# 401K Finder Pro

Find retirement plans, and the firms that hold and administer them, from the
U.S. Department of Labor's public Form 5500 filings.

Every U.S. employer-sponsored retirement plan covered by ERISA files a Form 5500
each year, and EBSA publishes the whole dataset. Those files answer a question
that is otherwise hard to answer: *who actually holds this 401(k), and who runs
it?* They also make it awkward. The data arrives as two dozen separate CSV
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
| 457(b) | plan name. 457 plans have no characteristics code of their own |
| SEP and SIMPLE | code `2N` (Code section 408 accounts and annuities) |
| Profit sharing | codes `2E`, `2A` |
| Money purchase / target benefit | codes `2C`, `2B` |
| ESOP | codes `2O`, `2P`, `2Q`, and Schedule R's ESOP boxes |
| Stock bonus | code `2I` |
| Defined benefit pension | codes `1A` to `1I` |
| Cash balance | code `1C` |
| Pooled employer plans (PEP) | code `2W`, and Schedule MEP |
| Multiemployer / multiple-employer | plan entity code, codes `2U` to `2X` |

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
  filing obligation. Code 2N appears only where a pension plan is funded
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
| **Form 5500-SF** | Trustee or custodian, self-contained. The most productive source for small-employer plans. | High |
| **Schedule A** | The insurance carrier holding annuity or insurance contracts. Often the only asset holder named for 403(b) and small plans. | High |
| **Schedule D Part 1** | Master trusts, collective trusts and pooled separate accounts holding plan assets. | High |
| **Schedule A Part 1** | Brokers receiving commissions. | High |
| **Form 5500 / SF** | Plan administrator, form preparer. | Medium / low |

Every one of these writes an evidence record naming the dataset, file, row,
field and acknowledgement ID it came from. `401k-finder plan <ein> --evidence`
prints the whole trail.

### Contacting them

The **Find plans** results carry a *Service providers by year* column and a
*Contact* column, and the plan's **Providers** tab lists each firm with the
years it covered, what it was paid, and how to reach it.

Telephone numbers come from two places and the application always says which.
A number marked **(filed)** was read out of the filing and cites its field:
employers file the plan administrator's number, their own, and for a small
plan the trustee or custodian's. Everything else, and every website, comes
from [`app/providers/directory.py`](app/providers/directory.py), a curated
list of the larger providers. That list exists because **no DOL dataset holds
a website**: 448 layouts, 1,278 distinct field names, not one URL. A test
asserts that, and will fail if DOL ever adds one.

The directory also records who took a business over, so a 2012 filing naming
Prudential Retirement points at Empower rather than reading as a dead end.

In the **Providers** tab, selecting a firm lists every company and plan that
names it, with the role and the years. It matches on the consolidated name, so
one selection covers every spelling the firm was filed under.

---

## Installing

### Windows

Download the installer from the releases page and run it. No Python required.
It installs both the desktop application and `401k-finder.exe`, the same
command line described below, in the install folder.

To build it yourself, see **[docs/DEPLOY.md](docs/DEPLOY.md)**, a step-by-step
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

This downloads the core datasets: the two main forms plus Schedules A, C Part 1
Item 2, D Part 1, H, I, R, DCG and MEP, which carry every provider field.
Expect a few gigabytes and 15 to 60 minutes depending on your connection.

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

### Index every year first

A full form year is 20 to 60 GB, so importing a decade to search a decade is not
realistic. Matching an employer to a plan needs only the two filing forms:

```bash
401k-finder index                    # every published year, employers only
401k-finder index --year 2015 --year 2016
```

That makes **Find my accounts** work across a whole career at a fraction of the
size. It cannot name a provider, because every asset holder is on a schedule. Once
you know which years matter, `sync` those in full. `401k-finder status` reports
which years are held at which depth, and the trace report says so too rather
than letting a thin year read as an empty one.

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
superseded filings removed. This is what you want. **All** includes every
filing received, including amendments and duplicates, and is useful only if you
are studying filing behaviour itself.

### Keeping the data on an external drive

A full seventeen years runs to several hundred gigabytes, which most laptops
cannot give up. The database, the downloads and the extracted CSV files can live
on any drive: external, USB, or a network share.

```bash
401k-finder storage              # where the data is now, and how much room is left
401k-finder storage list         # drives that could hold it
401k-finder storage set E:\401k-data
401k-finder storage reset        # move it back to this computer
```

In the desktop application the same controls are on the **Data** tab, under
*Where the data is kept*. Setting a new location moves whatever is already
there, so nothing has to be downloaded twice.

Only the bulk data moves. Settings, logs and the licence stay on the machine,
along with the small file recording where the data went. A pointer stored on
the drive it points at would leave with the drive.

Three things about removable media the application handles for you:

- **FAT32 is refused.** It cannot hold a file over 4 GB and a single form year
  passes that, so an import would die half way through with a disk-full error
  that is nothing of the kind. Reformat as exFAT or NTFS first. (Reformatting
  erases the drive, so copy anything you need off it beforehand.)
- **Network shares work, more slowly.** SQLite's write-ahead journal needs
  shared memory that network filesystems do not provide, so the database drops
  to the rollback journal there. A directly connected drive keeps the fast path.
- **An unplugged drive is reported, not worked around.** If the drive is missing
  at start-up you get a dialog offering to wait, choose another folder, or go
  back to internal storage. The application will not quietly create an empty
  database at the mount point, because an empty search result is
  indistinguishable from having lost everything.

Connect the drive before opening the application, and close the application
before ejecting it.

---

## Using it

### Desktop application

```bash
401k-finder-gui
```

Five tabs: **Find plans** (search, results, and a detail panel with the
provider list and full evidence), **Find my accounts** (trace your own old
401(k) from a work history, described below), **Providers** (which firms hold the
most plans, and drill into their book), **Provider changes** (which plans moved
between firms, and when), and **Data** (download years, import local files, see
what is loaded).

#### Themes

**View → Theme** offers seven schemes, and the choice is remembered:

| | |
|---|---|
| **Light** | The default. A plain, bright document look. |
| **Sepia** | Warm paper and dark brown. Less blue light for a long reading session. |
| **Dark** | Neutral greys with a blue accent, for low light. |
| **Midnight** | Deep navy with a periwinkle accent. Softer than Dark. |
| **Amber** | Warm near-black with the amber of the application mark. |
| **Hacker** | Near-black with a phosphor-green monospace treatment. |
| **High contrast** | Black, white and yellow with heavy borders, for low vision. |

They are defined in [`app/ui/theme.py`](app/ui/theme.py) as palettes of
semantic roles such as `accent`, `text_muted` and `danger`, rather than as separate
style sheets, so adding an eighth means adding one `Palette` and nothing else.

Every scheme is checked against WCAG contrast ratios by the test suite: body
text clears AAA on both the window and panel backgrounds, secondary text clears
AA, and the confidence colours clear the large-text threshold. High contrast is
held to AAA on every role it defines.
A test asserts that no colour appears in a generated style sheet unless the
palette supplied it, which is what stops a stray literal turning into the one
panel that never goes dark.

To adjust the look without editing the source, drop an `app.qss` into
`app/ui/resources/`. It is appended after whichever theme is active, so its
rules win. See [`app/ui/resources/README.md`](app/ui/resources/README.md).

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

## Finding your own old 401(k)

> **If you are looking for your own money rather than researching plans, read
> [docs/USER_GUIDE.md](docs/USER_GUIDE.md).** It is written for someone who has
> never heard of Form 5500, and the same guide is in the application under
> **Help → User guide**.

If you are trying to recover a retirement account from a previous employer,
the **Find my accounts** tab (or `401k-finder trace`) works from your work
history:

```bash
401k-finder trace \
    --employer "Acme Manufacturing" --state OH --from 2008 --to 2012 \
    --letters --output trace.txt
```

For each employer it reports the plan, its EIN and plan number, and **the firm
that was holding the money in the years you worked there**, which is often not
the firm holding it today. It also detects when a plan was wound up, and reads
the sponsor name *as filed at the time*, so an employer that has since been
acquired still matches under the name you remember.

The report ends with a letter you can send, with the plan's details already
filled in.

### What it cannot do, and why

**It cannot take a Social Security number, and no tool built on this data can.**
Form 5500 is what an employer files about a *plan*. Across all 448 published
record layouts there is no participant name, no Social Security number and no
individual balance. Every participant field is a count or an aggregate. There
is nothing for an SSN to match against.

So this tells you *which plan and who to ask*. It cannot confirm an account
exists in your name; only the plan's recordkeeper or a participant-level
registry can do that. Both the application and the report link to the ones that
take an SSN, chief among them the Department of Labor's
[Retirement Savings Lost and Found](https://lostandfound.dol.gov/).

An SSN typed into the employer box is detected, refused, and never written to
the database, the log or an exported report.

---

## Tracking providers over time

Every engagement is stored with the form year it was filed for, so with two or
more years imported the application can report which plans changed hands:

```bash
401k-finder changes --role RECORDKEEPER --year 2023
401k-finder changes --from-provider "Fidelity" --min-assets 10000000 --csv losses.csv
```

For each plan it gives the firm before, the firm after, the years compared, the
plan's size, and the schedule and field the later observation was read from, so
a surprising result can be checked against the filing rather than argued about.
The **Provider changes** tab is the same thing with filters and a CSV export.

A change means *the filings named a different firm*. That is usually a real
move, but a plan can rename or a filer can spell a firm two ways, which is why
provider names are consolidated first and every row carries its source.

---

## How the data fits together

The single most important fact about these files: **schedule datasets contain no
plan identity.** A Schedule H row is an `ACK_ID` and a hundred dollar amounts,
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

Financial totals need the same care. Form 5500 itself carries no asset figures:
for a large plan they are on Schedule H, for a small one on Schedule I, so
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

All 448 of them, 28 datasets across 17 form years from 2009 to 2025, are vendored
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
  licensing/             Signed offline licence keys, bound to one machine
  trace/                 Work-history matching for lost-account searches
  providers/             Name normalisation, brand table, fuzzy matching
  search/                Query objects and the FTS5-backed search engine
  evidence/              Evidence trail assembly
  services/              Sync, export, statistics
  ui/                    PySide6 window, widgets and background workers
database/
  migrations/            Schema snapshots (migrations live in code)
  seeds/                 Extra provider brands you can add without editing code
docs/                    Deployment, packaging and selling guides
installer/               PyInstaller spec and Inno Setup script
scripts/                 Layout refresh, test-data generation
tests/                   Test suite
```

---

## Development

Planned and possible improvements, ranked by value against effort, are in
[docs/ROADMAP.md](docs/ROADMAP.md).

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
  fuzzy match. That judgement is left to you, via
  `app/providers/matcher.py` and the seed file in `database/seeds/`.
- **Not every plan names a provider.** A small plan filing a 5500-SF with no
  trustee named will show none. That is the filing, not a bug.
- **Not an ERISA compliance tool.** This reads public filings and reports what
  they say. It does not evaluate fees, fiduciary conduct or plan health, and it
  is not advice.
- **Individual participants never appear.** Form 5500 reports plan-level data
  only: counts and totals, never people. There is no personal data here.

## Source and licence of the data

All data comes from the U.S. Department of Labor, Employee Benefits Security
Administration:

<https://www.dol.gov/agencies/ebsa/about-ebsa/our-activities/public-disclosure/foia/form-5500-datasets>

The filings are public records released under FOIA. Original filing images can
be retrieved from EBSA's [EFAST filing search](https://www.efast.dol.gov/5500search/)
using the sponsor EIN and plan number this application shows.
