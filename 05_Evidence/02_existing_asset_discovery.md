# 02 — Existing asset discovery (ran before any code was written)

## Locations searched

| # | Location / method | Query | Result |
|---|---|---|---|
| 1 | Whole user tree `C:\Users\LED 222` | `find -iname "*Return*Analysis*"` | Requirement PDF + CSV in `Downloads`; one project folder (row 3); Excel autosave/recent shortcuts only |
| 2 | Whole user tree | `find -iname "*kobiga*"` | Requirement files; unrelated kobiga dashboards (PPC, SKU, LPAF, Electricalsone MoM) — none return-related |
| 3 | `…\Abiraj\Project 14 ERA — eBay Return Analysis` | directory listing | **Requirement + skill documents only.** `Output Documents/` and `Gaps and Logics/` are **empty** — no dashboard, SQL or dataset was ever built |
| 4 | Whole user tree | `find -iname "*ebay_return*" -o -iname "*return_analysis*" -o -iname "*ERA*.sql"` | No SQL, no Python, no HTML. Only `TABLE_ebay_returns.md` skill copies + unrelated OneDrive/BQ files |
| 5 | Top-level project folders (74) | directory listing | No Return Analysis project existed. Adjacent-but-different: `eBay_Title_Optimization`, `eBay_Not_Listed_SKU_Checker`, `eBay_SKU_Gap_Analysis_Sharmilan`, `ebay_ppc_dashboard`, `At-a-Glance_Listing`, `REP-001_eBay_Listing_Before_After_Review` |
| 6 | Skill packs (`Downloads/skills`, `…/skills_minimal_pack*`, `LPAF…/Skill_Files`) | file listing + read | `TABLE_ebay_returns.md`, `TABLE_ppc.md`, `TABLE_order_transaction.md`, `TABLE_inv_final_stock.md` — table-level guidance, no report |
| 7 | `ledsone` database | `information_schema.columns` on the six in-scope schemas | Base tables only; **no** return-analysis view, materialised view or reporting table exists |
| 8 | Whole user tree, content search | `grep -ril "ebay_returns" --include=*.sql --include=*.py --include=*.md --include=*.js` | 42 hits, **all `.md`** — no SQL, Python or JS implementation anywhere. Surfaced one returns asset the name-pattern searches missed: **PH Returns Table System** (row 4 of the next table) |
| 9 | `tech_team_outputs.ph_task` (database `order_management_copy`) | `WHERE project_code='ERA'` / `project_name ILIKE '%return%'` | **18 existing ERA rows** — a live auto-monthly ERA publishing stream (row 5 of the next table). **This location was not searched in the original sweep** — see the correction below |

## Existing relevant assets found

| Asset | Path | Relevance | Decision |
|---|---|---|---|
| **REQ-14-D01 requirement document** | `…\Project 14 ERA — eBay Return Analysis\Requirement Documents\2026-07-20_abiraj_REQ-era_REQ-14-D01.md` | Prior governed spec for **this same report** (19 of today's 23 columns), with a graded column → `schema.table.column` Evidence Map, filter conditions and a reconciled June-2026 result | **REUSE** — its source map, its Returns/Return Rate/Return Rank/Return Cost definitions and its Known Limits are carried forward unchanged |
| **REQ-14-D01 skill document** | `…\Skills\2026-07-20__abiraj__era__REQ-14-D01.md` | Delivery discipline for the same stream | Followed |
| `TABLE_ebay_returns.md` skill | `Downloads/skills/` | Confirms the `res_his_order = 0` rule and the `seller_refund_amount` refund rule | Applied; the rule agrees with REQ-14-D01 |
| **PH Returns Table System** (tharsika, `PH_Return`, REQ-01-D01, 2026-07-28) | `Downloads/2026-07-28__tharsika__REQ-PH_Return_Req-01-D01.md`; dashboard at `/root/PHReturn/workflows/ph-returns-table-system/outputs/2026-07-28_ph_returns_table_system_v004.html` | A **delivered, published** returns dashboard covering Amazon + eBay | **Purpose-adjacent — not a duplicate.** Left canonical for its own purpose; see the comparison below |

### PH Returns Table System vs this report

Found by the content search (row 8), not by name — its project code is `PH_Return`,
so `*Return*Analysis*` never matched it. It is a genuine returns dashboard, so it was
compared field by field before the GREEN verdict was confirmed.

| Dimension | PH Returns Table System | This report |
|---|---|---|
| Organising axis | **PH user** (PH Name is a core field and filter) | Listing / SKU — no PH dimension at all |
| Grain | Individual return records + Amazon **ASIN** summary | eBay **Listing ID + SKU** |
| Channel | Amazon **and** eBay | eBay only |
| Source DB | `public.*` (denormalised layer) | `ledsone` normalised schemas — REQ-14-D01 explicitly rules the `public.*` layer out for this report |
| Return Rate | returns ÷ completed **order count** | returns ÷ ordered **units** (REQ-14-D01 definition) |
| Overlapping columns | SKU, Account, Marketplace, return count, return amount, Return Rate | same six |
| Columns it does **not** have | — | Listing ID, Product Title, Total Orders, Last Month/Last Year Returns and %, Refund vs Return Cost split, Main Return Reason, Return Rank, Negative Feedback, Open Cases, Stock, Ad Spend, Ad Sales, ACOS, ROAS — **14 of the 23 required columns** |

Per REQ-14-D01's own rule, purpose-adjacent objects stay canonical for their purpose
and this report complements them. PH Returns remains the truth for PH-user-level
Amazon + eBay return review; this report is the eBay Listing/SKU return analysis with
cost and advertising economics. Neither supersedes the other.

**Cross-report risk worth flagging:** the two dashboards compute **Return Rate
differently** (order count vs ordered units), so the same SKU can legitimately show
two different rates. This is the same open question as `04_gaps_and_limits.md` **G9**.

## CORRECTION (2026-09-17): the original GREEN verdict was incomplete

The first sweep searched the filesystem and the `ledsone` database, but **not the
`ph_task` publishing table**. Searching it during the publish step found **18 ERA
rows** — a live auto-monthly ERA stream by developer Abiraj that had **already
published an August 2026 Return Analysis dashboard on 2026-09-13** (ids 1501-1506),
covering the same period as this build.

The statement "no existing dashboard … produces the eBay Return Analysis output" was
therefore **wrong as written**. A published dashboard did exist. The corrected
position is below.

| ERA publish | ids | Recipients | HTML size | Notes |
|---|---|---|---|---|
| June 2026 | 518-523 | 6 | 520,837 | |
| July 2026 | 685-690 | 6 | 427,597 | kobiga's row marked `completed` |
| **August 2026** | **1501-1506** | **6** | **453,075** | same period as this build |

All three carry a stale `<title>` of "eBay Return Analysis — June 2026", but the
**content is genuinely per-month** (distinct md5 and length; the August row contains
August 2026 figures). The wrong title is a cosmetic bug in that publisher, not stale
data — worth reporting to its owner.

### Why this build is still not a duplicate

| | Existing ERA stream (Abiraj) | This build |
|---|---|---|
| Spec | REQ-14-D01, **19 columns**, abbreviated headers (`Rate`, `LM`, `LY`, `Neg FB`, `Rank`) | the kobiga PDF, **23 columns**, exact required names |
| Listing ID | absent | present |
| Market Place | absent | present |
| Last Month / Last Year Returns % | absent (counts only) | present |
| Extras | charts (`canvas`/`svg`), many controls | none beyond the 4 requested filters and 3 KPI cards |
| Recipients | 6 (no genga), `team = Development` | 7, `team = ebay_priors` |

## Duplicate-risk verdict: **AMBER — resolved by separation**

An existing published August 2026 ERA dashboard does exist, but it does **not**
satisfy the current requirement (it is missing 4 of the 23 required columns and
renames others). Rather than overwrite another developer's published rows, the
business decision (2026-09-17) was to publish this build under its **own project code
`RA`**, leaving the `ERA` stream completely untouched. Two distinct project codes, no
shared rows, nothing overwritten.

The original reasoning below remains valid for the filesystem and `ledsone`:
no SQL, script, view or table produces this output, and the ERA project folder's
`Output Documents/` is empty.

## Reuse / extend decision

**Extend REQ-14-D01, do not re-derive.** Today's requirement is REQ-14-D01's
19 columns plus 4: `Listing ID`, `Market Place`, `Last Month Returns %`,
`Last Year Returns %`. Everything REQ-14-D01 already graded is reused verbatim;
only the four new columns and the grain change (SKU → Listing + SKU) are new work.

### Deviations from REQ-14-D01, with reasons

| # | REQ-14-D01 said | This build does | Why |
|---|---|---|---|
| D1 | Grain = variant SKU | Grain = Listing ID + SKU | Today's requirement adds a `Listing ID` column; at SKU grain it would be multi-valued for 6 SKUs. 126 rows vs 120 |
| D2 | Open Cases = latest `to_state` ≠ CLOSED | `current_state` ≠ `'CLOSED'` on the `res_his_order = 0` row | `to_state` on that row is always `RETURN_REQUESTED`; `current_state` is the table's own current-status column and is populated on 133/133 rows |
| D3 | Ad = CPC from `performance_data` **+** CPS from `ebay_order_expenses` | Both campaign types from `performance_data` `*_listing_currency` | Avoids merging two unreconciled populations. See `04_gaps_and_limits.md` G3 |
| D4 | Return cost joined on `order_id` | Joined on `ebay_order_expenses.item_id` = the return's `transaction_id` | The `order_id`/`item_id` join returns **0 rows**. On FINAL_VALUE_FEE rows `item_id` is a 14-digit order-line id, not a listing id. Verified by digit-length profile |
