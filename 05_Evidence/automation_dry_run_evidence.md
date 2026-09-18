# Return Analysis automation — pre-enable dry run evidence

Run on 2026-09-18, **before** the monthly scheduler was registered, as the
critical validation test for the monthly automation. Nothing was published,
nothing was archived, and no production data was modified: every query was
read-only and both runs used `--dry-run`.

---

## Test 1 — August 2026, against the already-validated dashboard

```
python run.py --as-of 2026-09-01 --compare-with ..\04_Data\return_analysis_dataset.json
```

### Dates the automation calculated (nothing hardcoded)

| | Calculated | Required | |
|---|---|---|---|
| Execution date | 2026-09-01 | (simulated) | |
| Reporting period | 2026-08-01 to 2026-08-31 | August 2026 | PASS |
| Last Month | 2026-07-01 to 2026-07-31 | July 2026 | PASS |
| Last Year | 2025-08-01 to 2025-08-31 | August 2025 | PASS |

Half-open windows issued to the approved SQL, on the approved `request_date`
basis: `[2026-08-01, 2026-09-01)`, `[2026-07-01, 2026-08-01)`,
`[2025-08-01, 2025-09-01)`.

### Independent validation against the live database

**41 of 41 checks PASS**, covering **all 126 rows**:

- Returns, Return Rate, Total Orders
- Last Month Returns, Last Month Returns %, Last Month Refund (£)
- Last Year Returns, Last Year Returns %
- Refund (£), Return Cost (£), Main Return Reason, Return Rank
- Negative Feedback, Open Cases, Stock
- Ad Spend (£), Ad Sales (£), ACOS, ROAS
- duplicate Listing ID + SKU: none (126 rows, 126 distinct keys)
- join fan-out: none in any of the three windows (133 = 133, 118 = 118, 194 = 194)
- grand totals vs direct DB counts: 133 returns, £3,034.93 refund, 7 open cases
- KPI windows vs direct DB counts: 133 / 118 / 194
- rendered HTML equals the dataset on every cell; standalone, no external
  reference, no credential, header states the calculated periods

### Comparison with the validated August 2026 dashboard

| | Result |
|---|---|
| Row count | 126 = 126 |
| Row keys (Listing ID + SKU) | identical set |
| **22 period-locked columns × 126 rows** | **identical, every cell** |
| KPI windows | 133 / 118 / 194 = 133 / 118 / 194 |
| Period labels | identical |

**Last Month Returns = July 2026 and Last Year Returns = August 2025 reproduce
the validated values exactly on all 126 rows.**

### The two columns that moved, and why

43 cells differ, all in `Stock` (42) and `Open Cases` (1). Both are read as at
the moment of the run and cannot be restated for a past month:

- **Stock** — `inventory.local_inventory_current_stock_location_wise` holds
  current stock only. Already recorded as limit **G5** in
  `04_gaps_and_limits.md`. 42 SKUs moved between the reference snapshot
  (2026-09-17 12:07 UTC) and this one (2026-09-18 08:49 UTC).
- **Open Cases** — `current_state <> 'CLOSED'` is the return's status now.
  Return `5327549436` (listing 122989185800, SKU LDMG80B224) was open when the
  reference was built and reads `CLOSED` in the live database today, verified
  directly:

  ```
  return_id 5327549436 | res_his_order 0 | current_state CLOSED | requested 2026-08-24
  ```

  So 0 open cases is the correct current value, not a defect. The calculation
  is unchanged.

No other column moved. No requirement, formula or business rule was altered.

---

## Test 2 — 1 October 2026 simulation

```
python run.py --as-of 2026-10-01 --dates-only
python run.py --as-of 2026-10-01 --dry-run
```

### Dates the automation calculated

| | Calculated | Required | |
|---|---|---|---|
| Execution date | 2026-10-01 | (simulated) | |
| Reporting period | 2026-09-01 to 2026-09-30 | September 2026 | PASS |
| Last Month | 2026-08-01 to 2026-08-31 | August 2026 | PASS |
| Last Year | 2025-09-01 to 2025-09-30 | September 2025 | PASS |

Half-open windows: `[2026-09-01, 2026-10-01)`, `[2026-08-01, 2026-09-01)`,
`[2025-09-01, 2025-10-01)`.

### Full pipeline, not just the dates

The complete pipeline ran against the live database for that simulated date and
passed **41 of 41 independent checks on all 103 rows**:

- 103 Listing / SKU rows, 105 returns, £2,177.41 refund, 62 open cases
- KPI windows 105 (Sep 2026) / **133 (Aug 2026)** / 203 (Sep 2025)
- the Last Month figure of **133 is exactly the validated August 2026 total**,
  which is the strongest single proof that the windows genuinely shift

**September 2026 is an incomplete month** — the run date is 2026-09-18, so only
18 days of September exist. The figures are correct for the data that exists and
were not published. The real 1 October run will see the full month.

### Source-data validation surfaced genuine drift

Two return reasons appear in September that August did not have:
`FOUND_BETTER_PRICE` and `WITHDRAW_FROM_PURCHASE_CONTRACT`. They are reported as
a warning and shown verbatim — the requirement specifies raw source values, so
nothing was remapped or invented.

---

## No hardcoded month remains

`python test_automation.py` — all tests pass, including:

- the three scenarios in the requirement (1 Sep → Aug, 1 Oct → Sep, 1 Nov → Oct)
- 48 consecutive monthly runs (2025-01 through 2028-12) produce consistent windows
- year rollover (Jan 2027 → Dec 2026) and leap February (Mar 2028 → Feb 2028, 29 days)
- an AST scan of every production `.py` and `.ps1` in `automation/` finds **no
  calendar date literal in executable code**, and specifically none of
  `2026-08`, `2026-07`, `2025-08`, `August 2026`, `July 2026`, `August 2025`
- both approved SQL files render with only their six `params` CTE date literals
  substituted, proven by a round-trip that must reproduce the original byte for byte
