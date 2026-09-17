# eBay Return Analysis - validation report

- Source database: `ledsone` (read-only)
- Snapshot: 2026-09-17T05:09:52+00:00
- Reporting period: 2026-08-01 to 2026-08-31
- Rows: 126

## Checks

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | Grain unique (Listing ID + SKU) | **PASS** | 126 rows, 126 distinct keys |
| 2 | Return -> order line join is 1:1 (no fan-out) | **PASS** | join rows 133 = distinct returns 133 |
| 3 | Returns total = direct DB count | **PASS** | report 133 vs DB 133 |
| 4 | Refund total = direct DB sum | **PASS** | report 3034.93 vs DB 3034.93 |
| 5 | Open Cases total = direct DB count | **PASS** | report 10 vs DB 10 |
| 6 | Return Cost total = direct DB sum | **PASS** | report 332.54 vs DB 332.54 |
| 7 | Negative Feedback <= period total (rows are a subset of listings) | **PASS** | report 1 of 8 negative feedbacks in period |
| 8 | Allocated ad spend/sales never exceed the listing total (no double count) | **PASS** | 0 of 115 listings over-allocated |
| 9 | KPI window 'period' = direct DB count for 2026-08 | **PASS** | payload 133 vs DB 133 |
| 10 | KPI window 'last_month' = direct DB count for 2026-07 | **PASS** | payload 118 vs DB 118 |
| 11 | KPI window 'last_year' = direct DB count for 2025-08 | **PASS** | payload 194 vs DB 194 |
| 12 | KPI filtered slice (ledsone, last year) = direct DB count | **PASS** | payload 91 vs DB 91 |
| 13 | Account / Market Place single-valued per Listing+SKU | **PASS** | 0 rows with more than one account or marketplace |
| 14 | Return Rate = Returns / Total Orders x 100 | **PASS** | 0 mismatched rows |
| 15 | ACOS = Ad Spend / Ad Sales x 100 | **PASS** | 0 mismatched rows |
| 16 | ROAS = Ad Sales / Ad Spend | **PASS** | 0 mismatched rows |
| 17 | Return Rank = RANK() by Returns desc, Refund desc | **PASS** | 0 mismatched rows |
| 18 | Main Return Reason values are raw source values | **PASS** | unexpected: [] |
| 19 | Column set = requirement, in order, nothing extra | **PASS** | 23 columns |
| 20 | No null in identity / count fields | **PASS** | Listing ID=0, SKU=0, Product Title=0, Account=0, Market Place=0, Main Return Reason=0, Return Rank=0, Returns=0, Total Orders=0 |

## Null counts per required column

| Column | Nulls (of 126) |
|---|---|
| Listing ID | 0 |
| SKU | 0 |
| Product Title | 0 |
| Account | 0 |
| Market Place | 0 |
| Total Orders | 0 |
| Returns | 0 |
| Return Rate | 21 |
| Last Month Returns | 0 |
| Last Month Returns % | 62 |
| Last Year Returns | 0 |
| Last Year Returns % | 93 |
| Refund (£) | 0 |
| Return Cost (£) | 0 |
| Main Return Reason | 0 |
| Return Rank | 0 |
| Negative Feedback | 0 |
| Open Cases | 0 |
| Stock | 15 |
| Ad Spend (£) | 0 |
| Ad Sales (£) | 0 |
| ACOS | 39 |
| ROAS | 33 |
