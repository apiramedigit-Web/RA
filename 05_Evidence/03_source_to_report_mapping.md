# 03 — Source-to-report mapping

- **Source system:** PostgreSQL, database `ledsone`, connected read-only as `tech_user`
  (`WLP_SOURCE_DB_URL`). Schemas used: `customer_service`, `order_management`,
  `listings` *(not required in the end)*, `inventory`, `ebay_campaigns`, `accounting`.
- **Report grain:** one row per (`Listing ID`, `SKU`) with at least one return whose
  `request_date` falls in the reporting period. 126 rows for Aug 2026.
- **Windows:** period `2026-08-01 → 2026-09-01`, last month `2026-07-01 → 2026-08-01`,
  last year `2025-08-01 → 2025-09-01` — all half-open, all six literals in the
  `params` CTE of `02_SQL/ebay_return_analysis.sql`.

## Join spine (verified, not assumed)

| Edge | Keys | Cardinality check | Result |
|---|---|---|---|
| return → order line | `ebay_returns.transaction_id` = `order_item_info.item_transaction_id` | 133 join rows vs 133 distinct returns | **1:1, no fan-out** |
| return → listing | `ebay_returns.item_id` | 0 nulls; equals `order_item_info.item_id` on 133/133 | exact |
| order line → order | `order_item_info.order_id` = `orders.id` | 133/133 match | exact |
| order → account → channel | `orders.sub_source_id` → `sub_source.id` → `source.id`, `source_name = 'EBAY'` | — | channel filter |
| return → account | `ebay_returns.sub_source` = `sub_source.id` | 0 rows with >1 account per report row | single-valued |
| listing → ads | `performance_data.ebay_listing_id` = Listing ID | allocation ≤ listing total on 115/115 listings | no double count |
| returned line → fee | `ebay_order_expenses.item_id` = return `transaction_id` | 81 of 133 returns matched | partial (see G2) |
| feedback → order line | `ebay_orders_customer_feedbacks.transaction_id` = `item_transaction_id` | 8/8 negatives joined | exact |
| SKU → stock | `inventory.products.sku`; `products.id` = `local_inventory_current_stock_location_wise.inventory_id` | 4 location rows per product | exact, 15 SKUs unmatched (G1) |

## Column map

| # | Report Field | Source Table | Source Column | Join Key | Aggregation / Calculation | Grade |
|---|---|---|---|---|---|---|
| 1 | Listing ID | `customer_service.ebay_returns` | `item_id` | grain key | group key | VERIFIED |
| 2 | SKU | `order_management.order_item_info` | `COALESCE(NULLIF(real_sku,''), item_sku)` | `item_transaction_id` = `transaction_id` | group key | VERIFIED |
| 3 | Product Title | `order_management.order_item_info` | `item_title` | same | `MODE()` within group | VERIFIED |
| 4 | Account | `order_management.sub_source` | `map_name` | `sub_source.id` = `ebay_returns.sub_source` | `MODE()`; proven single-valued | VERIFIED |
| 5 | Market Place | `customer_service.ebay_returns` | `market_place_code` | grain | `MODE()`; proven single-valued. Displayed under a business label — see below | VERIFIED |
| 6 | Total Orders | `order_management.orders` ⋈ `source` ⋈ `order_item_info` | `item_quantity` (text → numeric) | `oi.order_id` = `o.id`; `source_name='EBAY'` | `SUM`, period, per Listing+SKU | VERIFIED |
| 7 | Returns | `customer_service.ebay_returns` | `return_id` | grain | `COUNT(DISTINCT)` where `res_his_order = 0`, period | VERIFIED |
| 8 | Return Rate | *derived* | — | — | `Returns / Total Orders * 100`; blank when Total Orders = 0 | VERIFIED |
| 9 | Last Month Returns | `customer_service.ebay_returns` | `return_id` | grain | `COUNT(DISTINCT)`, last-month window | VERIFIED |
| 10 | Last Month Returns % | *derived* | — | — | `Last Month Returns / last-month units * 100`; blank when 0 | VERIFIED |
| 11 | Last Year Returns | `customer_service.ebay_returns` | `return_id` | grain | `COUNT(DISTINCT)`, last-year window | VERIFIED |
| 12 | Last Year Returns % | *derived* | — | — | `Last Year Returns / last-year units * 100`; blank when 0 | VERIFIED |
| 13 | Refund (£) | `customer_service.ebay_returns` | `seller_refund_amount` | grain | `SUM`, period | VERIFIED *(currency, G4)* |
| 13b | Last Month Refund (£) | `customer_service.ebay_returns` | `seller_refund_amount` | grain | `SUM` over the same last-month returns as column 9 (`res_his_order = 0`, `request_date` in the last-month window), same Listing ID + SKU; £0 when none. **Business-approved addition 2026-09-17 — not one of the 23 PDF columns.** Same currency limit as Refund (G4) | VERIFIED *(currency, G4)* |
| 14 | Return Cost (£) | `accounting.ebay_order_expenses` | `fee` | `item_id` = return `transaction_id`; `transaction_type='REFUND'`, `fee_type IN (FINAL_VALUE_FEE, FINAL_VALUE_FEE_FIXED_PER_ORDER)` | `SUM` over the period's returned lines | **PARTIAL** (G2) |
| 15 | Main Return Reason | `customer_service.ebay_returns` | `reason` | grain | `MODE()` within group, raw source value | VERIFIED |
| 16 | Return Rank | *derived* | — | — | `RANK() OVER (ORDER BY Returns DESC, Refund DESC)` | VERIFIED |
| 17 | Negative Feedback | `customer_service.ebay_orders_customer_feedbacks` | `id` | `transaction_id` → order line → Listing+SKU | `COUNT(*)` where `type='Negative'`, period | VERIFIED |
| 18 | Open Cases | `customer_service.ebay_returns` | `current_state` | grain | `COUNT(DISTINCT return_id)` where `current_state <> 'CLOSED'` | VERIFIED |
| 19 | Stock | `inventory.products` ⋈ `local_inventory_current_stock_location_wise` | `stock` | `products.sku` = SKU; `inventory_id` = `products.id` | `SUM` over all 4 locations | **PARTIAL** (G1, G5) |
| 20 | Ad Spend (£) | `ebay_campaigns.performance_data` | `ad_fees_listing_currency` | `ebay_listing_id` = Listing ID, period | `SUM` per listing × row's unit share | **PARTIAL** (G3, G6) |
| 21 | Ad Sales (£) | `ebay_campaigns.performance_data` | `sale_amount_listing_currency` | same | `SUM` per listing × row's unit share | **PARTIAL** (G3, G6) |
| 22 | ACOS | *derived* | — | — | `Ad Spend / Ad Sales * 100` from the displayed figures; blank when Ad Sales = 0 | VERIFIED |
| 23 | ROAS | *derived* | — | — | `Ad Sales / Ad Spend` from the displayed figures; blank when Ad Spend = 0 | VERIFIED |

## Market Place display label

Business instruction (2026-09-17): show eBay UK as **`EBAY_UK`**, not the source code
`EBAY_GB`. This is a **presentation relabel only** — it is applied in
`03_Build/build_dashboard.py` (`MARKET_PLACE_LABELS`) when the HTML is rendered.

| Source value (`market_place_code`) | Shown in the report | Rows |
|---|---|---|
| `EBAY_GB` | **`EBAY_UK`** | 100 |
| `EBAY_DE` | `EBAY_DE` (verbatim, no label requested) | 23 |
| `EBAY_US` | `EBAY_US` (verbatim, no label requested) | 3 |

The database, `02_SQL/ebay_return_analysis.sql` and
`04_Data/return_analysis_dataset.json` all keep the raw `EBAY_GB`, so every
reconciliation in `validation_report.md` still ties back to the source. The Market
Place dropdown filters on the displayed label. `validate_html.py` asserts the relabel
is complete (no `EBAY_GB` left anywhere in the HTML) and that no other code was
touched.

## KPI cards (business request, 2026-09-17)

Three cards above the table: **This Month** (Aug 2026), **Last Month** (Jul 2026),
**Last Year** (Aug 2025) — each showing that month's **Returns**. They recompute for
every filter (Account, Market Place, SKU, Listing ID).

Fed by `02_SQL/return_kpi_windows.sql` → `kpi_windows` in the dataset JSON: the same
Returns metric (`COUNT(DISTINCT return_id)` where `res_his_order = 0`) over the same
eBay scope, grouped by the four fields the filters act on. No new metric is
introduced — Returns is required column 7, and the two comparison windows are
required columns 9 and 11.

| Card | Source | Default value | Reconciled to direct DB count |
|---|---|---|---|
| This Month | `ebay_returns`, Aug-2026 window | 133 | yes — and equals the table's Returns column total |
| Last Month | `ebay_returns`, Jul-2026 window | 118 | yes |
| Last Year | `ebay_returns`, Aug-2025 window | 194 | yes |

**A card is not the sum of the matching table column.** `Last Month Returns`
(column 9) counts July returns *for the same Listing+SKU that returned in August* —
it sums to 2. The Last Month **card** counts *all* July returns matching the filters —
118. Both are correct for their own question; the column is a per-row like-for-like,
the card is a month total.

### Known edge: comparison-window-only marketplaces

July 2026 contains **1 EBAY_CA and 1 EBAY_IE** return. Those marketplaces had no
August return, so they are not in the Market Place dropdown (which lists the reporting
period's marketplaces). They are counted in the `(All Market Places)` total of 118,
but selecting each listed marketplace in turn gives 82 + 33 + 1 = 116. The 2 missing
returns are real and correctly counted in the All view; they are simply not
individually selectable. `validate_html.py` asserts and reports this rather than
hiding it.

## Fan-out and double-count controls

| Risk | Control |
|---|---|
| Duplicate Listing+SKU rows | single `GROUP BY listing_id, sku`; asserted 126 rows = 126 distinct keys |
| Return counted twice | `res_his_order = 0` keeps one current row per return; `COUNT(DISTINCT return_id)` |
| Return history rows inflating counts | `res_his_order = 0` filter (source rule, `TABLE_ebay_returns.md` + REQ-14-D01) |
| Refund fee counted twice | `returned_lines` CTE is `SELECT DISTINCT` on `transaction_id` before the fee join |
| Order units double-counted | orders joined once via `orders.id`; channel restricted to `source_name = 'EBAY'` |
| Listing ad spend repeated on each SKU row | listing figure × `ad_share` = row units ÷ **all** period units on that listing; asserted never to exceed the listing total |
| Account / marketplace mis-mapped | asserted 0 report rows resolve to more than one account or marketplace |
