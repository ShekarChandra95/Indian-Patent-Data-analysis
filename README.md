# Patent Due-Date ETL

A small Python ETL pipeline that turns a raw Indian patent filing export
into client-level and case-level due-date analysis: which cases have an
outstanding **RQ (Request for Examination)** deadline, how urgent each
one is, and which clients need the most attention.

Built to replace a one-off spreadsheet exercise with something
repeatable, testable, and diffable: point it at a new export and it
regenerates the same analysis, deterministically, every time.

## Why RQ Due dates?

Under the Indian Patents Act, a Request for Examination must be filed
within 48 months of the priority/filing date, or the application is
treated as withdrawn. That's the deadline this pipeline tracks: cases
where an RQ due date exists but no RQ has been filed yet.

## Project layout

```
patent-due-date-etl/
├── src/patent_etl/
│   ├── config.py        # tunable constants (urgency windows, column map, statuses)
│   ├── extract.py        # reads the raw workbook sheet -> DataFrame
│   ├── transform.py       # cleans data, derives pending-RQ / client / status tables
│   ├── load.py            # writes results to sqlite / Excel / CSV
│   └── pipeline.py        # wires extract -> transform -> load together
├── scripts/
│   └── run_pipeline.py     # CLI entry point
├── tests/
│   └── test_transform.py    # unit tests against synthetic data (no real data needed)
├── data/
│   ├── raw/                  # put source .xlsx here (gitignored)
│   └── processed/             # gitignored scratch space
└── output/                     # pipeline outputs land here (gitignored)
```

## Setup

```bash
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

## Usage

1. Drop the source workbook into `data/raw/` (or point `--input`
   anywhere on disk).
2. Run the pipeline:

```bash
python scripts/run_pipeline.py --input data/raw/IndianPatentFilingDateNew.xlsx
```

This writes to `output/`:

- `patent_data.db` — SQLite database with `cases`, `pending_rq`,
  `client_summary`, `status_summary` tables
- `patent_due_date_report.xlsx` — formatted, multi-tab Excel report
- `csv/*.csv` — the same four tables as flat CSVs

Useful flags:

```bash
python scripts/run_pipeline.py \
  --input data/raw/IndianPatentFilingDateNew.xlsx \
  --output-dir output \
  --as-of 2026-08-08 \        # anchor "days remaining" math to a fixed date
  --due-soon-days 30 \        # urgency band 1 cutoff
  --due-later-days 90 \       # urgency band 2 cutoff
  --formats sqlite excel csv  # pick any subset
```

## Pipeline stages

| Stage | Module | Responsibility |
|---|---|---|
| Extract | `extract.py` | Read the correct sheet, drop blank trailing rows. No renaming or logic. |
| Transform | `transform.py` | Rename/clean columns, parse dates, split `Client Name / Ref.`, compute urgency buckets, aggregate to client- and status-level tables. |
| Load | `load.py` | Persist the resulting tables to sqlite, Excel, and/or CSV. |

Each stage is a plain function that takes a DataFrame (or dict of
DataFrames) and returns one — no hidden global state — so they're easy
to unit test and to reuse from a notebook.

### Output tables

- **`cases`** — one row per case, cleaned and typed, plus an `is_active`
  flag (false for Abandoned / Closed / Merged / Withdrawn).
- **`pending_rq`** — cases with an RQ due date and no RQ filed yet, with
  `days_remaining` and `urgency` (`OVERDUE`, `DUE <=30 DAYS`,
  `DUE <=90 DAYS`, `UPCOMING`) computed relative to `--as-of` (defaults
  to today).
- **`client_summary`** — one row per client: case counts by status,
  active pending-RQ count, overdue count, due-within-window count, and
  the client's nearest RQ due date.
- **`status_summary`** — case count and % share per status value.

## Running tests

```bash
pytest
```

Tests run against a small synthetic DataFrame shaped like the raw
export, so they don't require the real (private, client-confidential)
source file and run in well under a second.

## Design notes

- **Values, not spreadsheet formulas, in the Excel output.** The
  pipeline code is the single source of truth for how numbers are
  computed; the workbook is a generated, disposable artifact re-created
  on every run, not a place to hand-edit formulas.
- **Source data is never committed.** `data/raw/`, `data/processed/`,
  and `output/` are all gitignored — only `.gitkeep` placeholders are
  tracked, so client filing data never ends up in git history.
- **`config.py` centralizes every tunable value** (urgency windows,
  inactive statuses, the raw→clean column mapping) so a policy change
  is a one-line edit, not a search-and-replace across modules.

## License

Internal tooling — add a license here if this repo is going public.
