# 01 — Requirement extract

Source of truth: `01_Requirements/System Task - Return Analysis - kobiga.pdf`
(identical content also supplied as `… - kobiga.csv`; the CSV was used to read the
exact column spelling, because the PDF text layer runs the headers together).

The document contains exactly three things: a header row of 23 column names, two
illustrative sample rows, and a Metric/Formula table. Nothing else.

## 1. Required report columns (23, in document order)

| # | Column | # | Column |
|---|---|---|---|
| 1 | Listing ID | 13 | Refund (£) |
| 2 | SKU | 14 | Return Cost (£) |
| 3 | Product Title | 15 | Main Return Reason |
| 4 | Account | 16 | Return Rank |
| 5 | Market Place | 17 | Negative Feedback |
| 6 | Total Orders | 18 | Open Cases |
| 7 | Returns | 19 | Stock |
| 8 | Return Rate | 20 | Ad Spend (£) |
| 9 | Last Month Returns | 21 | Ad Sales (£) |
| 10 | Last Month Returns % | 22 | ACOS |
| 11 | Last Year Returns | 23 | ROAS |
| 12 | Last Year Returns % | | |

## 2. Required formulas (verbatim from the document)

| Metric | Formula |
|---|---|
| Return Rate % | Returns ÷ Total Orders × 100 |
| Last Month Return % | Last Month Returns ÷ Last Month Orders × 100 |
| Last Year Return % | Last Year Returns ÷ Last Year Orders × 100 |
| Return Cost per Return | Return Cost ÷ Returns |
| Refund per Return | Refund Amount ÷ Returns |
| Total Return Loss | Refund + Return Cost |
| Return Loss per Order | Total Return Loss ÷ Total Orders |
| ACOS | Ad Spend ÷ Ad Sales × 100 |
| ROAS | Ad Sales ÷ Ad Spend |

Return Cost per Return, Refund per Return, Total Return Loss and Return Loss per
Order are **not** in the 23 required columns, so per the task brief they are not
displayed. They are computable from displayed columns.

## 3. Required data concepts

- Return counting at Listing / SKU level.
- Three comparison windows: current period, last month, last year.
- `Last Month Orders` and `Last Year Orders` are named only as formula denominators,
  never as report columns — so they are computed but not displayed.

## 4. Sample rows in the document — read as illustrative, not as data

| Field | Row 1 | Row 2 |
|---|---|---|
| Listing ID | *(blank)* | *(blank)* |
| SKU | LS1001 | LS1025 |
| Product Title | Industrial Pendant Light | Edison Bulb 6 Pack |
| Account | LEDSONE | Electricalsone |
| Market Place | uk | DE |
| Return Rank | #1 | #2 |
| Last Month Returns % | *(blank)* | *(blank)* |
| Last Year Returns % | *(blank)* | *(blank)* |

Neither SKU (`LS1001`, `LS1025`) exists in the source database, and the Listing ID
cells are empty, so these are mock-ups. They fix **presentation** only: Return Rate
shown to 2 dp with a `%`, Return Rank shown as `#n`.

## 5. UNSPECIFIED — recorded, not invented

| # | Item | What the document says | Action taken |
|---|---|---|---|
| U1 | Reporting period | nothing | Latest complete month (Aug 2026) used; the query is parameterised by six date literals so any month can be run |
| U2 | Channel / marketplace scope | nothing | eBay, all marketplaces — carried from the prior governed spec REQ-14-D01 |
| U3 | Return Rank methodology | shows `#1`, `#2`; no rule | Carried from REQ-14-D01: `RANK()` by Returns desc, ties broken by Refund desc. **No new ranking invented.** |
| U4 | "Total Orders" — orders or units? | nothing | Ordered **units** (`SUM(item_quantity)`), carried from REQ-14-D01 where it is the graded-VERIFIED definition. Flagged in `04_gaps_and_limits.md` |
| U5 | Which warehouse "Stock" means | nothing | Sum of every warehouse location. Flagged |
| U6 | Row scope | nothing | Listing/SKU with ≥ 1 return in the period (the report's subject) |
| U7 | Currency handling | columns are labelled (£) | Source amounts are native currency (GBP/EUR/USD); **not** FX-converted. Flagged |
| U8 | Ad scope (CPC vs CPS) | nothing | Both, from one source. See `04_gaps_and_limits.md` G3 |
| U9 | Any dashboard behaviour (filters, charts, KPIs, sorting) | nothing | None added |

## 6. Required dashboard/report behaviour

The document specifies **no** interactive behaviour — no filters, no date controls,
no charts, no KPI cards, no search, no tabs. The deliverable is therefore a static
table of the 23 columns and nothing else.
