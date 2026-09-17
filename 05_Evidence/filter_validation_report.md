# eBay Return Analysis - filter / search behaviour validation

- File under test: `C:\Users\LED 222\eBay_Return_Analysis\06_Output\eBay_Return_Analysis.html`
- Driven in headless Chrome by dispatching real `change` / `input` / `click` events.
- Expected rows computed independently in Python from the dataset JSON.

| # | Check | Result | Detail |
|---|---|---|---|
| 1 | Page exposes all dataset rows to the filter | **PASS** | 126 filterable rows vs 126 in dataset |
| 2 | Scenario 1  defaults - no filter | **PASS** | 126 shown, expected 126 |
| 3 |    - empty-state row correct for 1 | **PASS** | shown=False, expected=False |
| 4 |    - row counter correct for 1 | **PASS** | "126 listing / SKU rows" |
| 5 |    - KPI cards correct for 1 | **PASS** | {'period': 133, 'last_month': 118, 'last_year': 194} vs expected {'period': 133, 'last_month': 118, 'last_year': 194} |
| 6 | Scenario 2  Account = ledsone | **PASS** | 56 shown, expected 56 |
| 7 |    - empty-state row correct for 2 | **PASS** | shown=False, expected=False |
| 8 |    - row counter correct for 2 | **PASS** | "56 of 126 listing / SKU rows" |
| 9 |    - KPI cards correct for 2 | **PASS** | {'period': 60, 'last_month': 37, 'last_year': 91} vs expected {'period': 60, 'last_month': 37, 'last_year': 91} |
| 10 | Scenario 3  Market Place = EBAY_UK | **PASS** | 100 shown, expected 100 |
| 11 |    - empty-state row correct for 3 | **PASS** | shown=False, expected=False |
| 12 |    - row counter correct for 3 | **PASS** | "100 of 126 listing / SKU rows" |
| 13 |    - KPI cards correct for 3 | **PASS** | {'period': 106, 'last_month': 82, 'last_year': 128} vs expected {'period': 106, 'last_month': 82, 'last_year': 128} |
| 14 | Scenario 4  Account + Market Place | **PASS** | 49 shown, expected 49 |
| 15 |    - empty-state row correct for 4 | **PASS** | shown=False, expected=False |
| 16 |    - row counter correct for 4 | **PASS** | "49 of 126 listing / SKU rows" |
| 17 |    - KPI cards correct for 4 | **PASS** | {'period': 53, 'last_month': 32, 'last_year': 71} vs expected {'period': 53, 'last_month': 32, 'last_year': 71} |
| 18 | Scenario 5  SKU exact 12IP67150 | **PASS** | 2 shown, expected 2 |
| 19 |    - empty-state row correct for 5 | **PASS** | shown=False, expected=False |
| 20 |    - row counter correct for 5 | **PASS** | "2 of 126 listing / SKU rows" |
| 21 |    - KPI cards correct for 5 | **PASS** | {'period': 3, 'last_month': 0, 'last_year': 1} vs expected {'period': 3, 'last_month': 0, 'last_year': 1} |
| 22 | Scenario 6  SKU partial 12IP | **PASS** | 15 shown, expected 15 |
| 23 |    - empty-state row correct for 6 | **PASS** | shown=False, expected=False |
| 24 |    - row counter correct for 6 | **PASS** | "15 of 126 listing / SKU rows" |
| 25 |    - KPI cards correct for 6 | **PASS** | {'period': 17, 'last_month': 8, 'last_year': 18} vs expected {'period': 17, 'last_month': 8, 'last_year': 18} |
| 26 | Scenario 7  Listing ID 163585 | **PASS** | 1 shown, expected 1 |
| 27 |    - empty-state row correct for 7 | **PASS** | shown=False, expected=False |
| 28 |    - row counter correct for 7 | **PASS** | "1 of 126 listing / SKU rows" |
| 29 |    - KPI cards correct for 7 | **PASS** | {'period': 2, 'last_month': 0, 'last_year': 2} vs expected {'period': 2, 'last_month': 0, 'last_year': 2} |
| 30 | Scenario 8  SKU + Listing ID | **PASS** | 4 shown, expected 4 |
| 31 |    - empty-state row correct for 8 | **PASS** | shown=False, expected=False |
| 32 |    - row counter correct for 8 | **PASS** | "4 of 126 listing / SKU rows" |
| 33 |    - KPI cards correct for 8 | **PASS** | {'period': 5, 'last_month': 0, 'last_year': 3} vs expected {'period': 5, 'last_month': 0, 'last_year': 3} |
| 34 | Scenario 9  all four combined | **PASS** | 1 shown, expected 1 |
| 35 |    - empty-state row correct for 9 | **PASS** | shown=False, expected=False |
| 36 |    - row counter correct for 9 | **PASS** | "1 of 126 listing / SKU rows" |
| 37 |    - KPI cards correct for 9 | **PASS** | {'period': 2, 'last_month': 0, 'last_year': 2} vs expected {'period': 2, 'last_month': 0, 'last_year': 2} |
| 38 | Scenario 10 SKU lower case 12ip | **PASS** | 15 shown, expected 15 |
| 39 |    - empty-state row correct for 10 | **PASS** | shown=False, expected=False |
| 40 |    - row counter correct for 10 | **PASS** | "15 of 126 listing / SKU rows" |
| 41 |    - KPI cards correct for 10 | **PASS** | {'period': 17, 'last_month': 8, 'last_year': 18} vs expected {'period': 17, 'last_month': 8, 'last_year': 18} |
| 42 | Scenario 11 no match at all | **PASS** | 0 shown, expected 0 |
| 43 |    - empty-state row correct for 11 | **PASS** | shown=True, expected=True |
| 44 |    - row counter correct for 11 | **PASS** | "0 of 126 listing / SKU rows" |
| 45 |    - KPI cards correct for 11 | **PASS** | {'period': 0, 'last_month': 0, 'last_year': 0} vs expected {'period': 0, 'last_month': 0, 'last_year': 0} |
| 46 | Scenario 12 Account = huettenlampen | **PASS** | 9 shown, expected 9 |
| 47 |    - empty-state row correct for 12 | **PASS** | shown=False, expected=False |
| 48 |    - row counter correct for 12 | **PASS** | "9 of 126 listing / SKU rows" |
| 49 |    - KPI cards correct for 12 | **PASS** | {'period': 10, 'last_month': 7, 'last_year': 20} vs expected {'period': 10, 'last_month': 7, 'last_year': 20} |
| 50 | Scenario 13 Market Place = EBAY_US | **PASS** | 3 shown, expected 3 |
| 51 |    - empty-state row correct for 13 | **PASS** | shown=False, expected=False |
| 52 |    - row counter correct for 13 | **PASS** | "3 of 126 listing / SKU rows" |
| 53 |    - KPI cards correct for 13 | **PASS** | {'period': 3, 'last_month': 1, 'last_year': 2} vs expected {'period': 3, 'last_month': 1, 'last_year': 2} |
| 54 | Scenario 14 mismatched account + market | **PASS** | 0 shown, expected 0 |
| 55 |    - empty-state row correct for 14 | **PASS** | shown=True, expected=True |
| 56 |    - row counter correct for 14 | **PASS** | "0 of 126 listing / SKU rows" |
| 57 |    - KPI cards correct for 14 | **PASS** | {'period': 0, 'last_month': 0, 'last_year': 0} vs expected {'period': 0, 'last_month': 0, 'last_year': 0} |
| 58 | Reset restores every control to its default | **PASS** | controls after reset: ['', '', '', ''] |
| 59 | Reset restores the KPI cards to the full month totals | **PASS** | cards after reset: {'period': '133', 'last_month': '118', 'last_year': '194'} |
| 60 | Reset shows all rows again | **PASS** | 126 of 126 rows visible |
| 61 | Case-insensitive SKU search: '12ip' == '12IP' | **PASS** | 15 rows both ways |
| 62 | Filtering never alters the underlying row data | **PASS** | all 126 rows byte-identical before and after every scenario |
