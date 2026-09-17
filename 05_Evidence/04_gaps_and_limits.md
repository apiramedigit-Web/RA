# 04 — Gaps and known limits

Every item below is a real source-data limitation. Nothing here was patched with an
invented value; affected cells are blank or £0 in the report.

## G1 — Stock is blank for 15 rows (14 distinct SKUs), all ending `-IDE`

`inventory.products` has no row for these SKUs. Evidence: for **all 14**, removing
the `-IDE` suffix finds exactly one product each.

```
24IP20240-IDE  12IP67505PK-IDE  12IP20600-IDE  12IP67100-IDE  12DE2P2A-IDE
12IP2080-IDE   12IP6715-IDE (×2) CCBKNWE50-IDE  CNP1000GB2PK-IDE
LDMST64E2782PK-IDE  LDDTFLE14122PK-IDE  CRSF100BM+PHHT1PBRBM+WCDCBM-IDE
LSFT220NB+RPR44WH-IDE  LSDO210BM+RPR44WH-IDE
```

A "strip the `-IDE` suffix before the stock lookup" rule would close all 15 rows, but
that rule appears nowhere in the requirement or in REQ-14-D01. **Not applied —
decision required.**

## G2 — Return Cost is £0 on 49 of 126 rows

Only 81 of the period's 133 returns have a matching refund-side selling-fee row in
`accounting.ebay_order_expenses` (61%). Report total £332.54, reconciled exactly to a
direct DB sum. Cause: a refund fee is only posted once the refund settles, so returns
that are still open — or that were never refunded — carry no fee row. REQ-14-D01
recorded the same limitation (~65% coverage) and graded the column PARTIAL.

## G3 — Two ad-cost sources disagree; they were **not** merged

| Source | Aug-2026 ad spend |
|---|---|
| `ebay_campaigns.performance_data`, `ad_fees_listing_currency`, both campaign types | **£14,302.09** *(CPC £8,488.21 + CPS £5,813.88)* |
| `accounting.ebay_order_expenses`, `AD_FEE` + `PREMIUM_AD_FEES` | **£17,228.14** |

REQ-14-D01 specified CPC spend from `performance_data` plus CPS spend from
`ebay_order_expenses`. That is not used here, because:

1. `performance_data.*_payout_currency` is **zero for every CPS row**, so REQ-14-D01's
   reading that the table is "CPC-only" holds for the payout columns but **not** for
   the `*_listing_currency` columns, which carry real CPS spend and sales.
2. `ebay_order_expenses` has an ad **fee** but no ad **sales** measure, and 20,119 of
   its 23,665 ad-fee rows (`PREMIUM_AD_FEES`) carry **no `order_id`**, so their revenue
   cannot be attributed at all. Pairing that spend with CPC-only sales would corrupt
   ACOS and ROAS.

This build therefore takes Ad Spend **and** Ad Sales from the single source that
carries both at listing grain, and reports the £2,926 difference rather than hiding
it. **Decision required if the business wants the expenses figure instead.**

## G4 — Amounts are native currency, not converted to £

`Refund` is `seller_refund_amount` in `seller_currency`: GBP 106 returns, EUR 24,
USD 3. Ad figures are in the listing's currency. No FX table exists in `ledsone`, so
no conversion was performed. Column headings keep the requirement's `(£)` label.
REQ-14-D01 recorded the same limit.

## G5 — Stock is a live snapshot, not period-bound

`local_inventory_current_stock_location_wise` holds current stock only; it is summed
across all four locations (UK, Germany, US, Canada). It cannot be restated as at the
end of the reporting period, and the requirement does not say which location is meant.

## G6 — Ad figures are allocated, not natively per-SKU

`performance_data` is per **listing**. For the 11 listings that contribute more than
one SKU row, the listing figure is split by each row's share of that listing's period
ordered units. A row's share of a listing with other, non-returned SKUs is therefore
below 100% — by design, so the figures stay per-SKU accurate. ACOS and ROAS are ratios
and are unaffected by the split.

## G7 — Return Rate is blank on 21 rows

Those Listing+SKU combinations had returns in August but no eBay units ordered in
August (the return belongs to an earlier order). Per REQ-14-D01, the rate is left
blank rather than shown as 0% or infinity.

## G8 — 36 returns per month carry only history rows

For Aug 2026, 169 distinct `return_id` values exist but only 133 have a
`res_his_order = 0` row; the other 36 have no `reason` on any row. The source rule
(`TABLE_ebay_returns.md` and REQ-14-D01) excludes them. Returns = 133.

## G9 — "Total Orders" is ordered units, not order count

The requirement does not define it. REQ-14-D01 defines it as `SUM(item_quantity)` and
grades it VERIFIED, so that definition is carried. If the business means
`COUNT(DISTINCT order_id)`, one line in the `order_units` CTE changes.

This now matters beyond this report: the **PH Returns Table System** (tharsika,
`PH_Return`, REQ-01-D01) computes Return Rate as returns ÷ completed **order count**,
while this report uses returns ÷ ordered **units**. Both are defensible and each
follows its own governed spec, but the same SKU can show two different Return Rates
across the two dashboards. Worth aligning deliberately rather than by accident —
see `02_existing_asset_discovery.md`.

## G10 — Return Rank is flat this period

The most any Listing+SKU returned in Aug 2026 is 2 (7 rows); the remaining 119 rows
returned 1 each. Ranks 1–126 are therefore decided mostly by the Refund tie-break.
This is what the data says, not a ranking defect.
