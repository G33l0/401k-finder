# Where to take this next

Improvements ranked by what they are worth against what they cost, for the two
audiences the product serves: an individual hunting their own money, and a
business that works with plans for a living.

Everything here is grounded in data the application already downloads, or in a
limitation observed in the code as it stands. Where something needs data that
does not exist, it says so.

**How to read the tables**

| | |
|---|---|
| **Effort** | S = days, M = a week or two, L = a month or more |
| **Value** | what it changes for the person using it, not a guess at revenue |

---

## 1. The three that matter most

These are ahead of everything else. Each removes a limitation a customer will
hit on their first serious use.

### 1.1 Follow the money when a plan is wound up — **S, high**

The trace report currently tells someone whose plan terminated: *"the filings do
not record where it went."*

That is not quite true, and the fix is small.
`F_SCH_H_PART1` carries **`PLAN_TRANSFER_EIN`**, **`PLAN_TRANSFER_NAME`** and
**`PLAN_TRANSFER_PN`** — the identity of the plan that received the assets.
Today the application reads that dataset only for the transferee's *name*, as if
it were a service provider, and the dataset is not in the core download set at
all, so an ordinary sync never fetches it.

Three changes turn that into the most valuable answer the product can give:

1. Add `F_SCH_H_PART1` to `CORE_DATASET_NAMES`.
2. Store the transfer as a **plan-to-plan link** (`from_plan`, `to_plan_ein`,
   `to_plan_number`, `form_year`), not a provider row.
3. Follow the chain in the trace: *"This plan wound up in 2016 and moved its
   assets to ACME HOLDINGS 401(K) PLAN, EIN 12-3456789 plan 002 — which is
   still filing, and its recordkeeper is Empower."*

"Where did my money go" is the hardest question in a lost-account search, and
for merged plans the answer is sitting in a file we already know how to parse.

### 1.2 A lightweight index across every year — **M, high**

The trace is only as good as the years imported, and a full year is 20–60 GB and
up to an hour. Someone who worked somewhere in 2011 needs 2011 data, so in
practice they must import a decade to search a decade. Most will not.

But employer matching needs almost nothing: sponsor name, EIN, plan number,
plan name, city, state, first/last year. That is a handful of columns from
`F_5500` and `F_5500_SF` — well under 1% of the bytes.

Add an **index-only sync**: fetch the two main forms for every year, keep the
identity columns, skip the schedules. A user could then trace across 2009–2025
in minutes and on a laptop, and be told exactly which years to import in full
for the provider detail on the plans that matched.

This is the single biggest constraint on the feature you just paid for.

### 1.3 Provider changes, year over year — **S, high (business)**

`PlanParty` already stores every engagement with its form year. Diffing
consecutive years for a plan yields the one thing every recordkeeper,
third-party administrator and advisory firm wants to buy:

> *These 43 plans changed recordkeeper last year. 19 left you. Here is who
> they went to, with assets and participant counts.*

No new data, no new parsing — a query and a report. It is the most commercially
valuable thing in the dataset and the cheapest to build.

---

## 2. For individuals

| Improvement | Effort | What it changes |
|---|---|---|
| **Successor-plan chain** (§1.1) | S | Answers "where did it go" for wound-up plans |
| **Index-only sync** (§1.2) | M | Makes a whole career searchable, not one year |
| **PDF output** | S | The claim letter arrives print-ready, not as a .txt. Fewer people give up at "now open this in Notepad" |
| **A case log** | M | Records who was written to, when, and what came back. Turns a one-off search into something a person can actually see through over the months these take |
| **Guided first run** | S | Someone opening this to find a lost 401(k) currently lands on an empty research tool. A short "what are you here for" prompt routing to *Find my accounts* would help |
| **Sponsor EIN history** | S | Same EIN, changed name over the years, shown as a timeline. Makes an acquisition legible |
| **Plan-size context** | S | "This plan had 1,200 participants and $410m" tells someone whether a small forgotten balance is plausible |
| **Print the registry list** | S | The list of places that take an SSN is the most useful page for someone whose employer never filed. Give it its own printable sheet |

**Not worth building:** anything that accepts a Social Security number. It is
covered in the README and `SELLING.md`, and it does not become possible with
more engineering — Form 5500 has no participant records. A test asserts this
against all 448 layouts.

---

## 3. For businesses

| Improvement | Effort | What it changes |
|---|---|---|
| **Provider change detection** (§1.3) | S | Win/loss reporting. The flagship business feature |
| **Fee benchmarking** | M | Schedule C carries `PROVIDER_OTHER_DIRECT_COMP_AMT` and indirect compensation; the forms carry participant counts and assets. Fee per participant, by plan size band and provider, with percentiles. Advisors sell on exactly this number |
| **Bulk trace** | S | `--history` already takes a CSV. Extend it to EINs, run unattended, write one report per employer. Serves TPAs and benefits consultants doing many at once |
| **Watchlists and alerts** | M | Track a set of EINs; on the next sync, report new filings, provider changes, large asset moves, terminations. Turns a one-off purchase into something opened weekly |
| **Prospect lists** | S | Plans by state, size band, provider and account type, exported to CSV. Most of the query already exists behind the search panel |
| **Scheduled sync** | S | A business will not remember to press Download. A Windows scheduled task plus `401k-finder sync` |
| **Shared database** | M | SQLite is per-machine. A read-only copy on a network share for a team, or an optional PostgreSQL backend. The data layer is already SQLAlchemy, so this is configuration and testing, not a rewrite |
| **Provider name curation** | M | `app/providers/matcher.py` does fuzzy consolidation, but a curated alias table ("Fidelity Investments Institutional Operations Company" → "Fidelity") would sharply improve every rollup and count. Ship the table as data, like the layouts |
| **Asset-mix analysis** | M | Schedule H breaks assets into categories — corporate debt, real estate, participant loans. Enables "plans like this hold X%" comparisons |
| **A documented Python API** | S | The layering is already clean. A short, stable public API plus examples lets a firm integrate this into their own pipeline — and makes a higher-priced tier defensible |

---

## 4. Product health — both audiences

| Improvement | Effort | Why |
|---|---|---|
| **Code signing** | S | Already flagged in `WINDOWS_APPLICATION.md` and still not done. A paid download that opens with *"Windows protected your PC"* will bleed refunds. This is the highest-value hour in the whole list |
| **Auto-update** | M | Customers currently have to be told a new version exists and reinstall by hand. With email-issued licences you have their address, but an in-app check is what actually gets people upgraded |
| **Column pruning on import** | M | 20–60 GB per form year is the biggest practical barrier to using the product. Most columns are never read. Importing only the columns the application uses would cut storage and import time several-fold |
| **Incremental re-sync** | M | DOL republishes years as filings arrive. Detect changed files rather than re-downloading a whole year |
| **Crash and support bundle** | S | One button that writes logs, schema version, imported years and licence status to a zip. Turns a confused email into a diagnosable one |
| **Accessibility pass** | M | Keyboard navigation, screen-reader labels, and a font-size setting. Some of the audience for a lost-pension tool are older users |
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
version would remove the 20–60 GB download that is the main obstacle for
individuals — but it also means hosting costs, a privacy policy covering data
you now hold, and a licence model that is no longer offline. Worth doing
deliberately or not at all.

**Pick one audience to lead with.** The individual features and the business
features pull the product in different directions — one toward a guided,
single-purpose wizard, the other toward a data console. The application
currently does both, which is fine while the feature set is small and will stop
being fine. §1.3 serves businesses and §1.1–1.2 serve individuals; whichever you
build first is a signal about which one you are selling to.
