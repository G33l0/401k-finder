# Where to take this next

Improvements ranked by what they are worth against what they cost, for the two
audiences the product serves: an individual hunting their own money, and a
business that works with plans for a living.

Section 1 is built. Everything from section 2 onwards is open for consideration.

Everything here is grounded in data the application already downloads, or in a
limitation observed in the code as it stands. Where something needs data that
does not exist, it says so.

**How to read the tables**

| | |
|---|---|
| **Effort** | S = days, M = a week or two, L = a month or more |
| **Value** | what it changes for the person using it, not a guess at revenue |

---

## 1. Shipped

The items that were ahead of everything else are built. Kept here because the
reasoning is the useful part, and because each has a limit worth knowing.

### 1.1 Follow the money when a plan is wound up ✅

`F_SCH_H_PART1` carries `PLAN_TRANSFER_EIN`, `PLAN_TRANSFER_NAME` and
`PLAN_TRANSFER_PN`, naming the plan that received a wound-up plan's assets. It is now
read as a plan-to-plan link into `plan_transfers` (schema v5) rather than as a
service provider, and the dataset joined the core download set.

The trace follows the chain across hops and reports who administers the plan at
the far end, so *"your plan was wound up in 2016, merged into this one, and
Empower holds it now"* replaces *"the filings do not record where it went"*.

**Limits.** A transferee whose year has never been imported stays unresolved.
Its name and EIN are still reported, and the link fills in by itself when that
year arrives. A plan that split assets across several transfers is followed
down the traceable one, and the report says so rather than presenting a guess
as a fact. Chains stop at 8 hops and detect loops, because real filings contain
both.

### 1.2 A lightweight index across every year ✅

`401k-finder index` fetches the two filing forms for every published year, which
are the identity columns employer matching needs, and the Data tab has **Index every
year**. Coverage is tracked per year at three depths, and both the trace report
and `status` say which years are thin, so "no match" in an index-only year
cannot be read as "no plan".

**Limits.** An index-only year can never name a recordkeeper: every asset holder
lives on a schedule. A 5500-SF filer does name its trustee on the form itself,
so the labels say "no provider schedules" rather than "no providers".

### 1.3 Provider changes, year over year ✅

`401k-finder changes` and the **Provider changes** tab compare each plan's filed
provider between adjacent *observed* years, filter by the firm that lost or won
the plan, aggregate the flows, and export to CSV.

**Limits.** A change means the filings named a different firm. Provider names
are consolidated first and the same engagement filed on two schedules is counted
once, but a plan can still rename or a filer spell a firm two ways, so every
row carries the schedule and field it was read from. Roles appearing and
disappearing are off by default: that usually means an unimported schedule, and
reporting it would read as a wave of losses that never happened.

### 1.4 Keep the data on an external drive ✅

Seventeen years is several hundred gigabytes, which was a hard ceiling on how
much of the archive anyone could actually hold. The database, downloads and
extracted CSVs now move to any drive, with `401k-finder storage set E:\401k-data`
or **Data → Where the data is kept**. Settings, logs, the licence and the
pointer itself stay on the machine, so the application still starts when the
drive is out.

**Limits.** FAT32 is refused rather than warned about: it caps a file at 4 GB
and a form year's database passes that, so an import would die half way through
with a misleading disk-full error. Network shares work but drop to the rollback
journal, because WAL needs shared memory that SMB and NFS do not implement. A
missing drive at start-up gets a dialog, never a silently recreated empty
database, because an empty search result is indistinguishable from having lost
everything.

### 1.5 Who serviced the plan, when, and how to reach them ✅

The filings hold one row per firm per role per year. `app/providers/servicing.py`
folds those into one line per firm carrying the years it covered, ordered so
whoever holds the money comes first. Find plans gained a providers-by-year
column and a contact column; the Providers tab lists every company using a
selected firm without leaving the tab.

Telephone numbers come from the filings where they exist (`ADMIN_PHONE_NUM`,
`SF_ADMIN_PHONE_NUM`, `SF_FDCRY_TRUSTE_CUST_PHONE_NUM`,
`FDCRY_TRUST_CUST_PHONE_NUM`, `PROVIDER_TERM_PHONE_NUM`) and are labelled
*(filed)* with their field. Schema 6 added the two on the filing forms; they
fill in on the next import and an old database keeps working meanwhile.

**Limits.** No DOL dataset holds a website, so those come from a curated list
of 49 firms in `app/providers/directory.py`, which the UI always marks as the
application's own addition. That list covers the national providers and will
never cover a small local trustee. It needs reviewing as firms are bought and
numbers change; `scripts/check_resources.py` checks the links.

---

## 2. For individuals

| Improvement | Effort | What it changes |
|---|---|---|
| **PDF output** | S | The claim letter arrives print-ready, not as a .txt. Fewer people give up at "now open this in Notepad" |
| **A case log** | M | Records who was written to, when, and what came back. Turns a one-off search into something a person can actually see through over the months these take |
| **Guided first run** | S | Someone opening this to find a lost 401(k) currently lands on an empty research tool. A short "what are you here for" prompt routing to *Find my accounts* would help |
| **Sponsor EIN history** | S | Same EIN, changed name over the years, shown as a timeline. Makes an acquisition legible |
| **Plan-size context** | S | "This plan had 1,200 participants and $410m" tells someone whether a small forgotten balance is plausible |
| **Print the registry list** | S | The list of places that take an SSN is the most useful page for someone whose employer never filed. Give it its own printable sheet |

**Not worth building:** anything that accepts a Social Security number. It is
covered in the README and `SELLING.md`, and it does not become possible with
more engineering, because Form 5500 has no participant records. A test asserts this
against all 448 layouts.

---

## 3. For businesses

| Improvement | Effort | What it changes |
|---|---|---|
| **Fee benchmarking** | M | Schedule C carries `PROVIDER_OTHER_DIRECT_COMP_AMT` and indirect compensation; the forms carry participant counts and assets. Fee per participant, by plan size band and provider, with percentiles. Advisors sell on exactly this number |
| **Bulk trace** | S | `--history` already takes a CSV. Extend it to EINs, run unattended, write one report per employer. Serves TPAs and benefits consultants doing many at once |
| **Watchlists and alerts** | M | Track a set of EINs; on the next sync, report new filings, provider changes, large asset moves, terminations. Turns a one-off purchase into something opened weekly |
| **Prospect lists** | S | Plans by state, size band, provider and account type, exported to CSV. Most of the query already exists behind the search panel |
| **Scheduled sync** | S | A business will not remember to press Download. A Windows scheduled task plus `401k-finder sync` |
| **Shared database** | M | SQLite is per-machine. A read-only copy on a network share for a team, or an optional PostgreSQL backend. The data layer is already SQLAlchemy, so this is configuration and testing, not a rewrite |
| **Provider name curation** | M | `app/providers/matcher.py` does fuzzy consolidation, but a curated alias table ("Fidelity Investments Institutional Operations Company" → "Fidelity") would sharply improve every rollup and count. Ship the table as data, like the layouts |
| **Asset-mix analysis** | M | Schedule H breaks assets into categories: corporate debt, real estate, participant loans. Enables "plans like this hold X%" comparisons |
| **A documented Python API** | S | The layering is already clean. A short, stable public API plus examples lets a firm integrate this into their own pipeline, and makes a higher-priced tier defensible |

---

## 4. Product health, for both audiences

| Improvement | Effort | Why |
|---|---|---|
| **Code signing** | S | Already flagged in `WINDOWS_APPLICATION.md` and still not done. A paid download that opens with *"Windows protected your PC"* will bleed refunds. This is the highest-value hour in the whole list |
| **Auto-update** | M | Customers currently have to be told a new version exists and reinstall by hand. With email-issued licences you have their address, but an in-app check is what actually gets people upgraded |
| **Column pruning on import** | M | 20 to 60 GB per form year is the biggest practical barrier to using the product. Most columns are never read. Importing only the columns the application uses would cut storage and import time several-fold |
| **Incremental re-sync** | M | DOL republishes years as filings arrive. Detect changed files rather than re-downloading a whole year |
| **Crash and support bundle** | S | One button that writes logs, schema version, imported years and licence status to a zip. Turns a confused email into a diagnosable one |
| **Accessibility pass** | M | The High contrast theme and the WCAG contrast floors on every scheme are done. What remains is keyboard navigation, screen-reader labels and a font-size setting. Some of the audience for a lost-pension tool are older users |
| **Link checking in CI** | S | `scripts/check_resources.py` exists but is run by hand. A monthly scheduled run would catch a dead registry link before a customer does |

---

## 5. Things worth deciding before building

**Data coverage is the honest ceiling.** Governmental 457(b) plans, church
plans that have not elected ERISA coverage, and one-participant plans filing
Form 5500-EZ are absent from this dataset entirely. No feature closes that gap.
Both the README and the trace report say so; keep it that way, because a
customer who discovers the limit themselves feels misled.

**A hosted version changes the business, not just the code.** Everything above
assumes the current shape: runs locally, no server, offline licence. A web
version would remove the 20 to 60 GB download that is the main obstacle for
individuals, but it also means hosting costs, a privacy policy covering data
you now hold, and a licence model that is no longer offline. Worth doing
deliberately or not at all.

**Pick one audience to lead with.** The individual features and the business
features pull the product in different directions: one toward a guided,
single-purpose wizard, the other toward a data console. The application
currently does both, which is fine while the feature set is small and will stop
being fine. §1.3 serves businesses and §1.1 and §1.2 serve individuals; whichever you
build first is a signal about which one you are selling to.
