# Return Analysis — completeness validation against the approved requirement

Run 2026-09-18. Discovery-first: nothing was rebuilt, nothing was recreated.
Every check below ran against the **existing** project assets and the **live**
`ledsone` database, read-only. No production data was modified.

Source of truth: `01_Requirements/System Task - Return Analysis - kobiga.csv`
(and the identical `.pdf`).

---

## 1. Discovery — existing assets found and reused

| # | Asset | Path | Status |
|---|---|---|---|
| 1 | Requirement document | `01_Requirements/…kobiga.pdf` + `.csv` | REUSED as source of truth |
| 2 | Source → report mapping | `05_Evidence/03_source_to_report_mapping.md` | REUSED |
| 3 | SQL logic | `02_SQL/ebay_return_analysis.sql`, `02_SQL/return_kpi_windows.sql` | REUSED, unchanged |
| 4 | Dashboard HTML | `06_Output/eBay_Return_Analysis.html` | VALIDATED, unchanged |
| 5 | Build scripts | `03_Build/extract_dataset.py`, `build_dashboard.py` | REUSED, unchanged |
| 6 | Automation | `automation/` (11 workflow modules + `run.py`) | REUSED, unchanged |
| 7 | Publisher | `03_Build/publish_ph_task.py` | REUSED, unchanged |
| 8 | Validation scripts | `03_Build/validate_dataset.py`, `validate_html.py`, `validate_filters.py`; `automation/validate_data.py`, `validate_dashboard.py` | REUSED, unchanged |
| 9 | Evidence | `05_Evidence/` (9 documents) | EXTENDED with this file only |
| 10 | Archive | `07_Archive/2026-08/` | PRESENT, unchanged |
| 11 | Documentation | `README.md`, `automation/README.md` | REUSED |

No duplicate asset was created. No unrelated project or file was touched.

---

## 2. Required-field coverage

All **23** required fields are present, in the requirement's order, with the
requirement's exact spelling.

| # | Required field | Present | Position |
|---|---|---|---|
| 1 | Listing ID | YES | 1 |
| 2 | SKU | YES | 2 |
| 3 | Product Title | YES | 3 |
| 4 | Account | YES | 4 |
| 5 | Market Place | YES | 5 |
| 6 | Total Orders | YES | 6 |
| 7 | Returns | YES | 7 |
| 8 | Return Rate | YES | 8 |
| 9 | Last Month Returns | YES | 9 |
| 10 | Last Month Returns % | YES | 10 |
| 11 | Last Year Returns | YES | 11 |
| 12 | Last Year Returns % | YES | 12 |
| 13 | Refund (£) | YES | 13 |
| 14 | Return Cost (£) | YES | 15 |
| 15 | Main Return Reason | YES | 16 |
| 16 | Return Rank | YES | 17 |
| 17 | Negative Feedback | YES | 18 |
| 18 | Open Cases | YES | 19 |
| 19 | Stock | YES | 20 |
| 20 | Ad Spend (£) | YES | 21 |
| 21 | Ad Sales (£) | YES | 22 |
| 22 | ACOS | YES | 23 |
| 23 | ROAS | YES | 24 |

**Missing required fields: none.**

### One non-requirement column is present — OPEN ITEM

`Last Month Refund (£)` occupies position 14, between `Refund (£)` and
`Return Cost (£)`. It is **not** in the requirement's 23 fields.

- `README.md` records it as "One column added on business approval
  (2026-09-17), directly after `Refund (£)`".
- `03_Build/validate_dataset.py` encodes it as
  "requirement + approved Last Month Refund".
- It does **not** alter `Refund (£)`, which remains the reporting-month
  (August 2026) refund, exactly as the requirement defines.

This is a documented approved addition that conflicts with a literal reading of
the 23-field list. **Raised for business decision; not removed unilaterally.**
See section 8.

---

## 3. Formula validation

Verified by recomputing each formula from the row's own displayed inputs and
comparing with what the dashboard shows, on all 126 rows.

| Requirement formula | Verified as | Result |
|---|---|---|
| Return Rate % = Returns ÷ Total Orders × 100 | recomputed per row | **PASS** 126/126 |
| Last Month Return % = Last Month Returns ÷ Last Month Orders × 100 | recomputed per row from independently queried July units | **PASS** 126/126 |
| Last Year Return % = Last Year Returns ÷ Last Year Orders × 100 | recomputed per row from independently queried Aug-2025 units | **PASS** 126/126 |
| ACOS = Ad Spend ÷ Ad Sales × 100 | recomputed per row | **PASS** 126/126 |
| ROAS = Ad Sales ÷ Ad Spend | recomputed per row | **PASS** 126/126 |

`Last Month Orders` and `Last Year Orders` are formula denominators only — the
requirement does not list them as fields, so they are computed but not shown.

### Four requirement formulas are not required fields

The requirement's Metric/Formula table names four measures that are **not** in
the 23-field list, so they are not displayed. All four derive from fields the
dashboard already shows — there is no data gap and nothing needs adding:

| Formula | Inputs (all displayed) | Computable |
|---|---|---|
| Return Cost per Return = Return Cost ÷ Returns | Return Cost (£), Returns | 126/126 rows |
| Refund per Return = Refund Amount ÷ Returns | Refund (£), Returns | 126/126 rows |
| Total Return Loss = Refund + Return Cost | Refund (£), Return Cost (£) | 126/126 rows |
| Return Loss per Order = Total Return Loss ÷ Total Orders | the above ÷ Total Orders | 105/126 rows |

The 21 rows where `Return Loss per Order` is undefined are the same 21 rows
where `Return Rate` is blank — returns in August against orders placed earlier,
so Total Orders is 0. Already recorded as limit **G7**.

Worked example (rank #1, SKU `24IP20240-IDE`, Returns 2, Total Orders 2,
Refund £82.62, Return Cost £13.54):
Return Rate 100.00% · Return Cost per Return £6.77 · Refund per Return £41.31 ·
Total Return Loss £96.16 · Return Loss per Order £48.08.

---

## 4. Data reconciliation — published dashboard vs live database

Independent reconciliation: every expected figure was derived from the base
tables with a query written for the check alone. The report query was **not**
reused, and `Main Return Reason` was re-derived from per-reason counts in Python
rather than with `MODE()`.

**38 of 41 checks PASS.** All 126 rows checked on every measure.

| Check | Result | Detail |
|---|---|---|
| Duplicate Listing ID + SKU rows | **PASS** | 126 rows, 126 distinct keys |
| Join fan-out, reporting window | **PASS** | 133 joined = 133 distinct returns |
| Join fan-out, last month window | **PASS** | 118 joined = 118 distinct returns |
| Join fan-out, last year window | **PASS** | 194 joined = 194 distinct returns |
| Listing ID ↔ SKU mapping | **PASS** | grain unique, no many-to-many |
| Account mapping | **PASS** | single-valued per Listing+SKU, 0 ambiguous |
| Marketplace mapping | **PASS** | single-valued per Listing+SKU, 0 ambiguous |
| Total Orders | **PASS** | 126/126 rows |
| Returns | **PASS** | 126/126 rows; total 133 = direct DB count |
| Return Rate | **PASS** | 126/126 rows |
| Last Month Returns | **PASS** | 126/126 rows |
| Last Month Returns % | **PASS** | 126/126 rows |
| Last Year Returns | **PASS** | 126/126 rows |
| Last Year Returns % | **PASS** | 126/126 rows |
| Refund (£) | **PASS** | 126/126 rows; total £3,034.93 = direct DB sum |
| Return Cost (£) | **PASS** | 126/126 rows; total £332.54 = direct DB sum |
| Main Return Reason | **PASS** | 126/126 rows, raw source values only |
| Return Rank | **PASS** | 126/126 rows, RANK() by Returns desc, Refund desc |
| Negative Feedback | **PASS** | 126/126 rows |
| Ad Spend (£) | **PASS** | 126/126 rows, no over-allocation on any listing |
| Ad Sales (£) | **PASS** | 126/126 rows |
| ACOS | **PASS** | 126/126 rows |
| ROAS | **PASS** | 126/126 rows |
| KPI window totals | **PASS** | 133 / 118 / 194 = direct DB counts |
| **Open Cases** | **FAIL** | 1 row differs; total 8 published vs 7 live |
| **Stock** | **FAIL** | 42 rows differ |

### The three failures are live-snapshot drift, not defects

The published dashboard is a snapshot taken **2026-09-17 12:07 UTC**. Two
approved columns are read as at the moment of the run and cannot be restated for
a past month:

- **Stock** — `inventory.local_inventory_current_stock_location_wise` holds
  current stock only. Already recorded as limit **G5**. 42 SKUs moved in the
  ~20 trading hours since the snapshot.
- **Open Cases** — `current_state <> 'CLOSED'` is the return's status *now*.
  Return `5327549436` (listing `122989185800`, SKU `LDMG80B224`) was open at
  snapshot time and reads `CLOSED` in the live database today. Verified
  directly:

  ```
  return_id 5327549436 | res_his_order 0 | current_state CLOSED | requested 2026-08-24
  ```

  So the live value of 0 is correct now, and the published value of 1 was
  correct then. The calculation did not change.

No requirement-locked column has drifted. **Raised for business decision in
section 8; nothing was republished.**

---

## 5. Period logic

Unchanged, as instructed.

| Window | Boundaries | Basis |
|---|---|---|
| Reporting period | `2026-08-01 <= request_date < 2026-09-01` | August 2026 |
| Last Month | `2026-07-01 <= request_date < 2026-08-01` | July 2026 |
| Last Year | `2025-08-01 <= request_date < 2025-09-01` | August 2025 |

`request_date` remains the date basis. Not substituted with order date, refund
date or anything else. Last Month and Last Year re-confirmed against the live
database on all 126 rows (section 4).

---

## 6. Standalone HTML

**27 of 27 checks PASS** (`03_Build/validate_html.py`):

- No external `src`/`href`, no `fetch()`, no `XMLHttpRequest`, no CSS `@import`
  — opens with no database, server or network
- 126 rows rendered, every row has all cells, every cell equals its dataset value
- 263 blank cells rendered against 263 nulls — a missing source value is never
  substituted with a number
- Exactly one table; no chart, canvas or svg element
- `EBAY_GB` fully relabelled to `EBAY_UK` (100 cells); `EBAY_DE` and `EBAY_US`
  shown verbatim

---

## 7. Filters

**62 of 62 checks PASS** (`03_Build/validate_filters.py`, driven in headless
Chrome with real `change` / `input` / `click` events; expectations computed
independently in Python).

Exactly the four approved controls plus Reset — Account, Market Place, SKU
search, Listing ID search. No form, no date picker, no extra input: 5 controls
total. 14 scenarios including combinations, partial and case-insensitive
matches, and a no-match empty state. Reset restores every control. Filtering
never alters the underlying row data.

**No additional filter was introduced.**

---

## 8. Open items requiring a business decision

Neither was actioned. Both are documented rather than solved.

| # | Item | Position |
|---|---|---|
| O1 | `Last Month Refund (£)` is present as a 24th column but is not one of the requirement's 23 fields. Recorded in `README.md` as approved on 2026-09-17. | Removing it changes a published deliverable that 7 task-board cards carry. Not removed unilaterally. |
| O2 | The published August 2026 snapshot no longer reconciles to live data on `Stock` (42 rows) and `Open Cases` (1 row), because both are live-read columns. | Refreshing means republishing August to the same 7 cards. Not republished unilaterally. |

---

## 9. Automation

**Unchanged and verified dynamically date-driven.** No second framework created.

| Check | Result |
|---|---|
| Run 2026-09-01 → Aug 2026 / Jul 2026 / Aug 2025 | **PASS** |
| Run 2026-10-01 → Sep 2026 / Aug 2026 / Sep 2025 | **PASS** |
| Run 2026-11-01 → Oct 2026 / Sep 2026 / Oct 2025 | **PASS** |
| 48 consecutive monthly runs produce consistent windows | **PASS** |
| No hardcoded calendar date in any production `.py` / `.ps1` | **PASS** (AST scan of executable code) |
| No `2026-08` / `2026-07` / `2025-08` / month-name hardcoding | **PASS** |
| Approved SQL reused with only the six `params` literals substituted | **PASS** (byte-for-byte round trip on both files) |

Scheduled task `RA_Monthly_Return_Analysis`, day 1 monthly at 07:00 local, next
run 2026-10-01. One scheduler only.

---

## 10. Publisher

**Scope unchanged.** Dry run (writes nothing) confirms:

- `project_code` `RA`, team `ebay_priors`, developer `Apirame`
- 7 members — genga, Jarsini, kobiga, powsteena, Sharmilan, Sivajitha, Thinesh
- ids **1713-1719**, upsert on `(project_code, assigned_user)`
- **Thasanan excluded**, publish aborts if a row for them ever appears

`ERA` stream verified untouched: 18 rows, ids 518-1506, last updated
**2026-09-13** — before any of this work. No unrelated user, project or
publisher path was modified.

---

## 11. Summary

| Area | Result |
|---|---|
| Required fields (23) | **PASS** — all present, correct order and spelling |
| Required formulas | **PASS** — all verified on 126/126 rows |
| Non-displayed formulas | **PASS** — all four computable from displayed fields |
| Duplicates / fan-out / aggregation | **PASS** |
| Account / Marketplace mapping | **PASS** |
| Last Month, Last Year, Refund | **PASS** — reconciled to live DB, all 126 rows |
| Standalone HTML | **PASS** — 27/27 |
| Filters | **PASS** — 62/62, exactly the four approved |
| Automation date-driven | **PASS** |
| Publisher scope | **PASS** — unchanged, ERA untouched |
| Live reconciliation | **38/41** — 3 failures, all live-snapshot drift (O2) |
| Column set | **OPEN** — one non-requirement column present (O1) |

No fabricated data. No invented business rule. No new metric, chart, card,
filter or section was added.
