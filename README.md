# eBay Return Analysis

Standalone HTML report for `System Task - Return Analysis - kobiga.pdf`.

**Deliverable:** `06_Output/eBay_Return_Analysis.html` — open it in any browser. All
data is embedded; it needs no database, server or network connection at runtime.

## Layout

| Folder | Contents |
|---|---|
| `01_Requirements/` | The requirement PDF and CSV, copied unchanged |
| `02_SQL/` | `ebay_return_analysis.sql` — the read-only dataset query; `return_kpi_windows.sql` — returns per KPI window |
| `03_Build/` | `extract_dataset.py`, `validate_dataset.py`, `build_dashboard.py`, `validate_html.py`, `validate_filters.py`, `publish_ph_task.py` |
| `04_Data/` | `return_analysis_dataset.json` — the validated dataset |
| `05_Evidence/` | Requirement extract, asset discovery, source mapping, gaps, validation reports |
| `06_Output/` | The standalone HTML report |

## Rebuilding

Needs `WLP_SOURCE_DB_URL` (or `ERA_SOURCE_DB_URL`) pointing at the `ledsone`
database. Every step is read-only — no write, no DDL is issued.

```
python 03_Build/extract_dataset.py     # run the SQL, save the dataset
python 03_Build/validate_dataset.py    # 20 checks vs independent direct DB counts
python 03_Build/build_dashboard.py     # render the standalone HTML
python 03_Build/validate_html.py       # 27 checks on the rendered file
python 03_Build/validate_filters.py    # 62 checks driving the filters in headless Chrome
```

`build_dashboard.py` only reads the dataset — rendering never rewrites `04_Data/`.

## Filtering and search

The report has four combining controls plus Reset: **Account** (default
`(All Accounts)`), **Market Place** (default `(All Market Places)`), **SKU** search
and **Listing ID** search. Both searches are case-insensitive substring matches, and
all four conditions apply together (AND). Dropdown options are generated from the
embedded data. Filtering only shows and hides existing rows — no value is
recalculated, and the row counter in the header reflects what is currently shown.

## KPI cards

Three cards show **Returns** for this month (Aug 2026), last month (Jul 2026) and the
same month last year (Aug 2025) — 133 / 118 / 194 unfiltered. They recompute for
every filter combination. Each card is that month's true return count, so a card is
deliberately **not** the sum of the matching table column (see
`05_Evidence/03_source_to_report_mapping.md`).

If you change the reporting period, update the six date literals in
`02_SQL/return_kpi_windows.sql` to match `ebay_return_analysis.sql`.

## Publishing to the task board

```
python 03_Build/publish_ph_task.py --dry-run   # show what would change, write nothing
python 03_Build/publish_ph_task.py             # publish
```

Publishes to `tech_team_outputs.ph_task` (database `order_management_copy`, via
`DATABASE_URL`) under **project_code `RA`**, team `ebay_priors`, one card for each of
the 7 members — genga, Jarsini, kobiga, powsteena, Sharmilan, Sivajitha, Thinesh.
**Thasanan is excluded by instruction** and the publish aborts if a row for them ever
appears.

It upserts on `project_code` + `assigned_user`, so re-running updates the same seven
rows rather than adding more. Everything happens in one REPEATABLE READ transaction
that verifies the stored `md5(html_content)` against the file and the row count for
`RA` (scoped to the project code, never the whole table) **before** committing; any
mismatch rolls the whole publish back.

> `RA` is deliberately separate from the existing **`ERA`** project code, which is a
> different developer's auto-monthly Return Analysis stream on the older 19-column
> spec. The two never share a row. See `05_Evidence/02_existing_asset_discovery.md`.

The server frequently runs out of connection slots; `--attempts` and `--wait` tune the
connection retry.

## Changing the reporting period

Edit the six date literals in the `params` CTE at the top of
`02_SQL/ebay_return_analysis.sql`, then update `reporting_period`,
`last_month_period` and `last_year_period` in `03_Build/extract_dataset.py`.
Nothing else is period-dependent.

## Current run

- Reporting period **2026-08-01 → 2026-08-31** (latest complete month), last month
  2026-07, last year 2025-08.
- 126 Listing / SKU rows · 133 returns · Refund £3,034.93 · Return Cost £332.54.
- Source `ledsone`, snapshot 2026-09-17 04:38 UTC (each rebuild re-stamps this; the
  live figure is `snapshot_utc` in `04_Data/return_analysis_dataset.json` and in the
  report header).
- 16/16 data checks and 13/13 HTML checks pass. See `05_Evidence/`.

Known limits are listed in `05_Evidence/04_gaps_and_limits.md` — read it before
using Stock, Return Cost or the ad columns.
