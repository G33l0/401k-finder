# Test data

Synthetic DOL-shaped CSV files used by the test suite and for trying the
application without downloading tens of gigabytes from the Department of Labor.

The files are **not** committed — they are generated on demand, because every
one of them uses the real published column set for its dataset and year, and
those column sets are already vendored in
[`app/dol/layouts/data/`](../app/dol/layouts/data).

## Generating them

```bash
python -m scripts.make_test_data --year 2023 --plans 48
```

Then load them:

```bash
401k-finder import test_data --year 2023
401k-finder search acme
```

## What is real and what is not

**Real:** the file names, the column names, the column order, and the codes —
plan characteristics codes (`2E2G2J`), Schedule C service codes (`1537645038`),
plan-entity codes, filing statuses. Everything structural comes from the DOL
layouts, so a bug in parsing shows up here exactly as it would in production.

**Invented:** every value. The employers, EINs, plan names, dollar amounts and
provider assignments are fabricated. The provider names are real firm names
because name normalisation and the brand table are part of what is being
tested, but their attachment to these fictional plans is not.

Do not treat anything generated here as a factual statement about any real
employer, plan or provider.

## What the generator deliberately covers

- Large plans filing Form 5500 with Schedules H, C, D and R attached, and small
  plans filing Form 5500-SF with Schedule I — the two very different paths
  through the importer.
- Financial totals that live only on Schedule H, which is what proves the
  filing-enrichment step works.
- Every branch of the plan classifier: 401(k), 403(b), 457(b), SEP/SIMPLE,
  ESOP, money purchase, profit sharing, defined benefit and pooled employer.
- Schedule C rows with packed service codes, so role assignment is exercised.
- Placeholder provider names (`N/A`, `NONE`, `SAME AS ABOVE`, `-`, `0`) that
  the extractor must reject rather than store as providers.
