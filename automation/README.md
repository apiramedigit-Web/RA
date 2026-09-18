# Return Analysis (RA) — monthly automation

Rebuilds, validates and publishes the approved eBay Return Analysis dashboard
on the 1st of every month. It does **not** re-implement the report: the
business logic stays in `02_SQL/`, the renderer stays in
`03_Build/build_dashboard.py` and the publisher stays in
`03_Build/publish_ph_task.py`. This folder drives those approved artefacts and
supplies the one thing they lacked — a reporting period worked out from the
date the run starts.

## Reporting period

Calculated at run time, never hardcoded:

| Run date | Reporting period | Last Month | Last Year |
|---|---|---|---|
| 1 Sep 2026 | Aug 2026 | Jul 2026 | Aug 2025 |
| 1 Oct 2026 | Sep 2026 | Aug 2026 | Sep 2025 |
| 1 Nov 2026 | Oct 2026 | Sep 2026 | Oct 2025 |

All three windows are half-open calendar months — `start <= request_date < end`
— on the approved `request_date` basis. `request_date` is not substituted with
order date, refund date or anything else.

The six dates go into the `params` CTE at the top of each approved query, and
**only** those six literals are substituted; `fetch_data.render_sql()` proves it
by putting the file's own dates back and demanding the original file byte for
byte. If that round trip ever fails, the run aborts rather than execute an
altered query.

## Workflow

Follows the Common Automation Workflow, one module per step:

| # | Step | Module |
|---|---|---|
| 1 | Scheduler / Trigger | `scheduler.ps1` |
| 2 | Configuration | `config.py` |
| 3 | Fetch Data | `fetch_data.py` |
| 4 | Validate Source Data | `validate_data.py` |
| 5 | Process Business Logic | `process_data.py` |
| 6 | Transform Data | `transform_data.py` |
| 7 | Generate Output | `generate_dashboard.py` |
| 8 | Validate Output | `validate_dashboard.py` |
| 9 | Publish / Store Output | `publish.py` |
| 10 | Archive | `archive.py` |
| 11 | Logging | `logger.py` |

`run.py` orchestrates them. Any failing stage stops the run **before** the
publish stage, so a bad month leaves the previous report and the published task
cards exactly as they were.

## Running it

```
python run.py                        full monthly run (what the scheduler calls)
python run.py --dry-run              everything except publish and archive
python run.py --as-of 2026-10-01     simulate a run on that date
python run.py --dates-only           print the calculated periods, touch nothing
python run.py --preflight            environment readiness check only
python run.py --compare-with <file>  dry run, then diff against a known dataset
python test_automation.py            date-logic and no-hardcoding tests, no DB
```

`--dry-run` writes its evidence to `.work/` so `05_Evidence/` is left alone.

## Scheduler

```
powershell -ExecutionPolicy Bypass -File .\scheduler.ps1 -Mode register
powershell -ExecutionPolicy Bypass -File .\scheduler.ps1 -Mode status
```

Task `RA_Monthly_Return_Analysis`, day 1 of every month at 07:00 local.
Registration inspects an existing task and repairs it in place rather than
creating a second one, and `-Mode status` reports any *other* scheduled task
that points at this automation.

The separate **`ERA`** stream — a different developer's Return Analysis
publishing under its own project code — is never read, written or scheduled by
anything here.

## Environment

Both must be set at **USER** level so the scheduled task inherits them. Neither
is ever written to a file, a log, the dataset or the dashboard.

| Variable | Database | Used for |
|---|---|---|
| `WLP_SOURCE_DB_URL` (or `ERA_SOURCE_DB_URL`) | `ledsone` | the source, read-only |
| `DATABASE_URL` | `order_management_copy` | `tech_team_outputs.ph_task` publish |

`python run.py --preflight` checks both without touching anything.

## Validation

**Step 4 — source.** Required tables exist, each window holds data, no duplicate
returns, no join fan-out in any window, no orphan returns, Account / Market Place
mapping complete and single-valued per Listing + SKU, required fields populated,
return reasons known, advertising and stock sources present. A hard finding stops
the run; a soft finding is logged and carried into the evidence file. Nothing is
patched with an invented value.

**Step 8 — output.** Every expected figure is derived here from the base tables
with a query written for the check alone. The report query is not reused, and
Main Return Reason is deliberately re-derived from per-reason counts in Python
rather than with `MODE()`, so a fault in the report cannot reproduce itself in
the check. All rows are checked on Returns, Return Rate, Last Month Returns and
%, Last Year Returns and %, Refund, Last Month Refund, Return Cost, Main Return
Reason, Return Rank, Negative Feedback, Open Cases, Stock, Ad Spend, Ad Sales,
ACOS and ROAS — plus duplicate Listing ID + SKU, join fan-out, and a render check
that every HTML cell equals its dataset value.

Evidence lands in `05_Evidence/automation_source_validation_report.md` and
`05_Evidence/automation_validation_report.md`, and a copy of both goes into the
month's archive folder.

**Not automated:** `03_Build/validate_filters.py` drives the four filters in
headless Chrome. Its scenarios name specific August SKUs, so it stays a manual
check — run it after a month if you want the filter behaviour re-proven. The
automated Step 8 still confirms the controls are exactly the four approved
filters plus Reset.

## Publish and archive

**Publish.** The validated staging files replace the live deliverables
(`04_Data/return_analysis_dataset.json`, `06_Output/eBay_Return_Analysis.html`),
the HTML via an atomic `os.replace`. Then the approved publisher runs unchanged:
project_code `RA`, team `ebay_priors`, the same seven members, Thasanan still
excluded, still an upsert on `(project_code, assigned_user)` inside one
REPEATABLE READ transaction that verifies the stored md5 before committing.
Scope is not widened, and `ERA` is not touched.

**Archive.** `07_Archive/<YYYY-MM>/` holds each month's HTML, dataset,
validation result, both evidence files and a `run_info.json`. Folders are named
for the month they report on and are **never overwritten** — a re-run of the
same month lands in `<YYYY-MM>_02`. Before the live files are replaced, the
outgoing report is preserved too if its month has no folder yet, which is how
the hand-built August 2026 report is kept on the first automated run.

The seven `RA` task-board cards are an upsert by design — that is the approved
publisher's existing behaviour, so the card always shows the current month while
the archive holds the history.

## Logging

`logs/execution.log`, `logs/error.log` and `logs/last_run_summary.json`, which
always carries the execution date, the calculated reporting month, the Last
Month and Last Year periods, the source row count, the generated row count, the
validation result, the publish result and any errors. A failed run also writes
`logs/FAILURE_NOTICE.txt`, cleared on the next success. A DSN can never reach a
log — the logger scrubs it.

## Two columns move when a month is re-run

`Stock` and `Open Cases` are read as at the moment of the run and cannot be
restated for a past month (`Stock` is limit **G5** in
`05_Evidence/04_gaps_and_limits.md`; `Open Cases` is `current_state <> 'CLOSED'`,
so a return that closes later stops counting as open). Re-running a month
therefore legitimately changes them while every other column stays identical.
`--compare-with` reports the two separately for that reason — it never hides
them, and neither calculation was changed.
