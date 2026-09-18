# eBay Return Analysis - standalone HTML validation

- File: `C:\Users\LED 222\eBay_Return_Analysis\06_Output\eBay_Return_Analysis.html`
- Size: 174,104 bytes
- Rows rendered: 126

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | No external src/href (standalone) | **PASS** | 0 external references found: [] |
| 2 | Runtime independence: no external script | **PASS** |  |
| 3 | Runtime independence: no fetch() | **PASS** |  |
| 4 | Runtime independence: no XMLHttpRequest | **PASS** |  |
| 5 | Runtime independence: no CSS @import | **PASS** |  |
| 6 | Header row = required columns, in order, nothing extra | **PASS** | 24 headers |
| 7 | Row count = dataset row count | **PASS** | 126 rendered vs 126 in dataset |
| 8 | Every row has all 24 cells | **PASS** | 126 rows checked |
| 9 | Every rendered cell equals its dataset value | **PASS** | 0 mismatches |
| 10 | Missing values render blank, never substituted | **PASS** | 263 blank cells rendered vs 263 nulls in dataset |
| 11 | No chart / canvas / svg element | **PASS** |  |
| 12 | Exactly one table | **PASS** | 1 tables |
| 13 | Controls are exactly the requested four filters + Reset | **PASS** | found ['f-account', 'f-listing', 'f-market', 'f-reset', 'f-sku'] |
| 14 | No unrequested control (form, date picker, extra input) | **PASS** | 5 controls total |
| 15 | Account dropdown default is (All Accounts) | **PASS** | first option ('', '(All Accounts)') |
| 16 | Account dropdown options = distinct values in the data | **PASS** | 10 options |
| 17 | Market Place dropdown default is (All Market Places) | **PASS** | first option ('', '(All Market Places)') |
| 18 | Market Place dropdown options = distinct values in the data | **PASS** | 3 options |
| 19 | Row filter keys match the row's own displayed values | **PASS** | 0 mismatches |
| 20 | EBAY_GB fully relabelled to EBAY_UK everywhere | **PASS** | 0 occurrences of EBAY_GB left; 100 cells show EBAY_UK (expected 100) |
| 21 | Market Place codes with no business label are shown verbatim | **PASS** | verbatim: ['EBAY_DE', 'EBAY_US'] |
| 22 | KPI payload embedded in the page (no runtime fetch) | **PASS** | 436 entries |
| 23 | KPI payload totals equal the dataset's window totals | **PASS** | period=133, last_month=118, last_year=194 |
| 24 | Every Market Place in the dropdown is present in the KPI payload | **PASS** | dropdown: ['EBAY_DE', 'EBAY_UK', 'EBAY_US'] |
| 25 | Comparison-window-only marketplaces are counted in the All total | **PASS** | ['EBAY_CA', 'EBAY_IE'] - 2 returns, reachable only with Market Place = (All Market Places) |
| 26 | KPI 'this month' total equals the Returns column total | **PASS** | 133 vs 133 |
| 27 | Exactly three KPI cards, all labelled Returns | **PASS** | 3 cards |
