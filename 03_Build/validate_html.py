"""Validate the standalone HTML against the dataset it was built from.

Writes 05_Evidence/html_validation_report.md.
"""
import html as htmllib
import json
import pathlib
import re

BASE = pathlib.Path(__file__).resolve().parent.parent
DATA = json.loads((BASE / "04_Data" / "return_analysis_dataset.json").read_text(encoding="utf-8"))
HTML_FILE = BASE / "06_Output" / "eBay_Return_Analysis.html"
OUT = BASE / "05_Evidence" / "html_validation_report.md"

doc = HTML_FILE.read_text(encoding="utf-8")
results = []

# Market Place is shown under a business label; everything else is shown verbatim.
# Declared here independently of the builder so this stays a real check.
MARKET_PLACE_LABELS = {"EBAY_GB": "EBAY_UK"}


def shown(row):
    label = MARKET_PLACE_LABELS.get(row["Market Place"])
    return dict(row, **{"Market Place": label}) if label else row


SHOWN_ROWS = [shown(r) for r in DATA["rows"]]


def check(name, ok, detail):
    results.append((name, "PASS" if ok else "FAIL", detail))


# 1. standalone - no network reference of any kind at runtime
external = re.findall(r'(?:src|href)\s*=\s*"(?!#)([^"]+)"', doc)
remote = [u for u in external if re.match(r'(https?:)?//|^data:|^file:', u)]
check("No external src/href (standalone)", not remote and not external,
      f"{len(external)} external references found: {external[:5]}")
for pattern, label in [(r"<script[^>]*\ssrc\s*=", "no external script"),
                       (r"fetch\s*\(", "no fetch()"),
                       (r"XMLHttpRequest", "no XMLHttpRequest"),
                       (r"@import", "no CSS @import")]:
    check(f"Runtime independence: {label}", not re.search(pattern, doc, re.I), "")

# 2. header row matches the required column list exactly, in order
head_html = re.search(r"<thead>(.*?)</thead>", doc, re.S).group(1)
headers = [htmllib.unescape(h) for h in re.findall(r"<th[^>]*>(.*?)</th>", head_html, re.S)]
check("Header row = required columns, in order, nothing extra",
      headers == DATA["columns"], f"{len(headers)} headers")

# 3. every dataset row is rendered, once
body_html = re.search(r"<tbody>(.*?)</tbody>", doc, re.S).group(1)
all_tr = re.findall(r"<tr\b([^>]*)>(.*?)</tr>", body_html, re.S)
tr_attrs = [a for a, _ in all_tr if "no-match" not in a]
tr = [inner for a, inner in all_tr if "no-match" not in a]
check("Row count = dataset row count", len(tr) == DATA["row_count"],
      f"{len(tr)} rendered vs {DATA['row_count']} in dataset")
check("Every row has all 23 cells",
      all(len(re.findall(r"<td[^>]*>.*?</td>", r, re.S)) == 23 for r in tr),
      f"{len(tr)} rows checked")

# 4. rendered values reproduce the dataset values (no drift, no fabrication)
MONEY = {"Refund (£)", "Return Cost (£)", "Ad Spend (£)", "Ad Sales (£)"}
PERCENT = {"Return Rate", "Last Month Returns %", "Last Year Returns %", "ACOS"}
INTEGER = {"Total Orders", "Returns", "Last Month Returns", "Last Year Returns",
           "Negative Feedback", "Open Cases", "Stock"}


def expected(column, value):
    if value is None:
        return ""
    if column in MONEY:
        return f"£{value:,.2f}"
    if column in PERCENT:
        return f"{value:,.2f}%"
    if column == "ROAS":
        return f"{value:,.2f}"
    if column == "Return Rank":
        return f"#{value}"
    if column in INTEGER:
        return f"{value:,.0f}"
    return str(value)


mismatch = []
for row_html, row in zip(tr, SHOWN_ROWS):
    cells = [htmllib.unescape(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)]
    for column, rendered in zip(DATA["columns"], cells):
        want = expected(column, row[column])
        if rendered != want:
            mismatch.append(f'{row["SKU"]}/{column}: "{rendered}" != "{want}"')
check("Every rendered cell equals its dataset value", not mismatch,
      f"{len(mismatch)} mismatches" + (f" e.g. {mismatch[:3]}" if mismatch else ""))

# 5. blanks stay blank - a missing source value is never filled with a number
blank_expected = sum(1 for r in SHOWN_ROWS for c in DATA["columns"] if r[c] is None)
blank_rendered = sum(
    1 for row_html in tr
    for c in re.findall(r"<td[^>]*></td>", row_html)
)
check("Missing values render blank, never substituted",
      blank_expected == blank_rendered,
      f"{blank_rendered} blank cells rendered vs {blank_expected} nulls in dataset")

# 6. nothing beyond the report is rendered
check("No chart / canvas / svg element", not re.search(r"<(canvas|svg)\b", doc, re.I), "")
check("Exactly one table", len(re.findall(r"<table\b", doc)) == 1,
      f"{len(re.findall(r'<table\b', doc))} tables")

# 7. the only controls are the four requested filters plus Reset
control_ids = re.findall(r'<(?:input|select|button)\b[^>]*\bid="([^"]+)"', doc)
check("Controls are exactly the requested four filters + Reset",
      sorted(control_ids) == ["f-account", "f-listing", "f-market", "f-reset", "f-sku"],
      f"found {sorted(control_ids)}")
check("No unrequested control (form, date picker, extra input)",
      not re.search(r"<form\b", doc, re.I)
      and not re.search(r'type="(date|month|week|datetime-local|range)"', doc, re.I)
      and len(re.findall(r"<(?:input|select|button)\b", doc, re.I)) == 5,
      f"{len(re.findall(r'<(?:input|select|button)\b', doc, re.I))} controls total")

# 8. dropdown options come from the data, with the required default first
def option_values(select_id):
    block = re.search(rf'<select id="{select_id}">(.*?)</select>', doc, re.S).group(1)
    return re.findall(r'<option value="([^"]*)">(.*?)</option>', block, re.S)

for select_id, column, all_label in [("f-account", "Account", "(All Accounts)"),
                                     ("f-market", "Market Place", "(All Market Places)")]:
    opts = option_values(select_id)
    want = sorted({r[column] for r in SHOWN_ROWS})
    check(f"{column} dropdown default is {all_label}",
          opts[0] == ("", all_label), f"first option {opts[0]}")
    check(f"{column} dropdown options = distinct values in the data",
          [v for v, _ in opts[1:]] == want and [t for _, t in opts[1:]] == want,
          f"{len(opts) - 1} options")

# 9. filter keys on each row agree with that row's displayed values
key_mismatch = []
for attrs, row in zip(tr_attrs, SHOWN_ROWS):
    got = dict(re.findall(r'data-(\w+)="([^"]*)"', attrs))
    want = {"account": row["Account"], "market": row["Market Place"],
            "sku": row["SKU"].lower(), "listing": str(row["Listing ID"]).lower()}
    want = {k: htmllib.unescape(htmllib.escape(v)) for k, v in want.items()}
    if {k: htmllib.unescape(v) for k, v in got.items()} != want:
        key_mismatch.append(f'{row["SKU"]}: {got} != {want}')
check("Row filter keys match the row's own displayed values", not key_mismatch,
      f"{len(key_mismatch)} mismatches" + (f" e.g. {key_mismatch[:2]}" if key_mismatch else ""))

# 10. the Market Place relabel is complete, and relabels nothing else
market_col = DATA["columns"].index("Market Place")
market_cells = [
    htmllib.unescape(re.findall(r"<td[^>]*>(.*?)</td>", row_html, re.S)[market_col])
    for row_html in tr
]
market_options = [v for v, _ in option_values("f-market")][1:]

for raw, label in MARKET_PLACE_LABELS.items():
    n_expected = sum(1 for r in DATA["rows"] if r["Market Place"] == raw)
    check(f"{raw} fully relabelled to {label} everywhere",
          len(re.findall(rf"\b{re.escape(raw)}\b", doc)) == 0
          and market_cells.count(label) == n_expected
          and label in market_options,
          f"{len(re.findall(rf'\\b{re.escape(raw)}\\b', doc))} occurrences of {raw} left; "
          f"{market_cells.count(label)} cells show {label} (expected {n_expected})")

unlabelled = {r["Market Place"] for r in DATA["rows"]} - set(MARKET_PLACE_LABELS)
check("Market Place codes with no business label are shown verbatim",
      all(market_cells.count(v) == sum(1 for r in DATA["rows"] if r["Market Place"] == v)
          and v in market_options for v in unlabelled),
      f"verbatim: {sorted(unlabelled)}")

# 11. the KPI payload is embedded, self-consistent and uses the same labels
kpi_payload = json.loads(
    re.search(r'<script id="kpi-data" type="application/json">(.*?)</script>', doc, re.S).group(1))
check("KPI payload embedded in the page (no runtime fetch)",
      len(kpi_payload) == len(DATA["kpi_windows"]),
      f"{len(kpi_payload)} entries")
check("KPI payload totals equal the dataset's window totals",
      all(sum(d["n"] for d in kpi_payload if d["w"] == w)
          == sum(k["returns"] for k in DATA["kpi_windows"] if k["window_key"] == w)
          for w in ("period", "last_month", "last_year")),
      ", ".join(f'{w}={sum(d["n"] for d in kpi_payload if d["w"] == w)}'
                for w in ("period", "last_month", "last_year")))
check("Every Market Place in the dropdown is present in the KPI payload",
      set(market_options) <= {d["m"] for d in kpi_payload},
      f'dropdown: {market_options}')
# A comparison window may contain a marketplace that had no return in the reporting
# period, so it is in the totals but not in the dropdown. Correct - but reported.
window_only = sorted({d["m"] for d in kpi_payload} - set(market_options))
check("Comparison-window-only marketplaces are counted in the All total",
      all(any(d["m"] == m and d["w"] != "period" for d in kpi_payload) for m in window_only),
      f"{window_only or 'none'} - "
      f'{sum(d["n"] for d in kpi_payload if d["m"] in window_only)} returns, '
      "reachable only with Market Place = (All Market Places)")
check("KPI 'this month' total equals the Returns column total",
      sum(d["n"] for d in kpi_payload if d["w"] == "period")
      == sum(r["Returns"] for r in DATA["rows"]),
      f'{sum(d["n"] for d in kpi_payload if d["w"] == "period")} vs '
      f'{sum(r["Returns"] for r in DATA["rows"])}')
n_cards = len(re.findall(r'<div class="kpi">', doc))
check("Exactly three KPI cards, all labelled Returns",
      n_cards == 3 and len(re.findall(r'<span class="kpi-unit">Returns</span>', doc)) == 3,
      f"{n_cards} cards")

lines = ["# eBay Return Analysis - standalone HTML validation", "",
         f"- File: `{HTML_FILE}`",
         f"- Size: {HTML_FILE.stat().st_size:,} bytes",
         f"- Rows rendered: {len(tr)}", "",
         "| # | Check | Result | Detail |", "|---|---|---|---|"]
for i, (name, verdict, detail) in enumerate(results, 1):
    lines.append(f"| {i} | {name} | **{verdict}** | {detail} |")
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

failed = [r for r in results if r[1] == "FAIL"]
for name, verdict, detail in results:
    print(f"{verdict:4} {name} {('- ' + detail) if detail else ''}")
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed -> {OUT}")
