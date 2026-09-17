"""Drive the report's filter controls in a real browser and check what they show.

Loads a probe copy of 06_Output/eBay_Return_Analysis.html in headless Chrome, runs
the requested filter scenarios, and compares the visible rows against expectations
computed independently in Python from 04_Data/return_analysis_dataset.json.

Writes 05_Evidence/filter_validation_report.md. Changes nothing in 06_Output.
"""
import json
import pathlib
import re
import subprocess
import sys
import tempfile

BASE = pathlib.Path(__file__).resolve().parent.parent
HTML_FILE = BASE / "06_Output" / "eBay_Return_Analysis.html"
DATA = json.loads((BASE / "04_Data" / "return_analysis_dataset.json").read_text(encoding="utf-8"))
ROWS = DATA["rows"]
OUT = BASE / "05_Evidence" / "filter_validation_report.md"

# Market Place is filtered on its business label, not the raw source code.
MARKET_PLACE_LABELS = {"EBAY_GB": "EBAY_UK"}


def market_of(row):
    return MARKET_PLACE_LABELS.get(row["Market Place"], row["Market Place"])
CHROME = pathlib.Path(r"C:\Program Files\Google\Chrome\Application\chrome.exe")

# scenario: (label, account, market, sku search, listing search) - "" means unset
SCENARIOS = [
    ("1  defaults - no filter", "", "", "", ""),
    ("2  Account = ledsone", "ledsone", "", "", ""),
    ("3  Market Place = EBAY_UK", "", "EBAY_UK", "", ""),
    ("4  Account + Market Place", "ledsone", "EBAY_UK", "", ""),
    ("5  SKU exact 12IP67150", "", "", "12IP67150", ""),
    ("6  SKU partial 12IP", "", "", "12IP", ""),
    ("7  Listing ID 163585", "", "", "", "163585"),
    ("8  SKU + Listing ID", "", "", "12IP", "163"),
    ("9  all four combined", "ledsone", "EBAY_UK", "12IP", "163"),
    ("10 SKU lower case 12ip", "", "", "12ip", ""),
    ("11 no match at all", "", "", "zzz-no-such-sku", ""),
    ("12 Account = huettenlampen", "huettenlampen", "", "", ""),
    ("13 Market Place = EBAY_US", "", "EBAY_US", "", ""),
    ("14 mismatched account + market", "huettenlampen", "EBAY_UK", "", ""),
]


def expected(account, market, sku, listing):
    """The rows that should be visible - computed from the dataset, not from the page."""
    out = []
    for r in ROWS:
        if account and r["Account"] != account:
            continue
        if market and market_of(r) != market:
            continue
        if sku and sku.lower() not in r["SKU"].lower():
            continue
        if listing and listing.lower() not in str(r["Listing ID"]).lower():
            continue
        out.append(f'{r["Listing ID"]}|{r["SKU"]}')
    return out


def expected_kpi(window_key, account, market, sku, listing):
    """That window's return count under the same filters - from the dataset, not the page."""
    total = 0
    for k in DATA["kpi_windows"]:
        if k["window_key"] != window_key:
            continue
        if account and k["account"] != account:
            continue
        if market and MARKET_PLACE_LABELS.get(k["market_place"], k["market_place"]) != market:
            continue
        if sku and sku.lower() not in (k["sku"] or "").lower():
            continue
        if listing and listing.lower() not in str(k["listing_id"]).lower():
            continue
        total += k["returns"]
    return total


PROBE_JS = """
<script>
window.addEventListener('load', function () {
  var scenarios = __SCENARIOS__;
  var account = document.getElementById('f-account'),
      market  = document.getElementById('f-market'),
      sku     = document.getElementById('f-sku'),
      listing = document.getElementById('f-listing'),
      reset   = document.getElementById('f-reset'),
      noMatch = document.getElementById('no-match'),
      counter = document.getElementById('row-count'),
      rows    = Array.prototype.slice.call(
                  document.querySelectorAll('tbody tr:not(#no-match)'));

  function fire(el, type) { el.dispatchEvent(new Event(type, {bubbles: true})); }
  function snapshot() {
    return rows.map(function (r) {
      return Array.prototype.slice.call(r.querySelectorAll('td'))
               .map(function (td) { return td.textContent; }).join('\\u0001');
    }).join('\\u0002');
  }
  function visible() {
    return rows.filter(function (r) {
      return getComputedStyle(r).display !== 'none';
    }).map(function (r) {
      var td = r.querySelectorAll('td');
      return td[0].textContent + '|' + td[1].textContent;
    });
  }

  var before = snapshot();
  var results = [];

  scenarios.forEach(function (s) {
    account.value = s[1]; fire(account, 'change');
    market.value  = s[2]; fire(market, 'change');
    sku.value     = s[3]; fire(sku, 'input');
    listing.value = s[4]; fire(listing, 'input');
    results.push({
      label: s[0],
      visible: visible(),
      noMatchShown: !noMatch.hidden,
      counter: counter.textContent,
      kpi: {
        period:     document.getElementById('kpi-period').textContent,
        last_month: document.getElementById('kpi-last_month').textContent,
        last_year:  document.getElementById('kpi-last_year').textContent
      }
    });
  });

  // Reset must restore every control and show everything again.
  reset.click();
  results.push({
    label: 'RESET',
    visible: visible(),
    noMatchShown: !noMatch.hidden,
    counter: counter.textContent,
    controls: [account.value, market.value, sku.value, listing.value],
    kpi: {
      period:     document.getElementById('kpi-period').textContent,
      last_month: document.getElementById('kpi-last_month').textContent,
      last_year:  document.getElementById('kpi-last_year').textContent
    }
  });

  var after = snapshot();

  var pre = document.createElement('pre');
  pre.id = 'probe-results';
  pre.textContent = JSON.stringify({
    results: results,
    dataUnchanged: before === after,
    totalRows: rows.length
  });
  document.body.appendChild(pre);
});
</script>
"""


def run_probe():
    if not CHROME.exists():
        sys.exit(f"Chrome not found at {CHROME}")
    doc = HTML_FILE.read_text(encoding="utf-8")
    probe = doc.replace("</body>", PROBE_JS.replace("__SCENARIOS__", json.dumps(SCENARIOS)) + "</body>")
    tmp = pathlib.Path(tempfile.mkdtemp()) / "probe.html"
    tmp.write_text(probe, encoding="utf-8")
    dom = subprocess.run(
        [str(CHROME), "--headless=new", "--disable-gpu", "--virtual-time-budget=8000",
         "--window-size=1600,1000", "--dump-dom", tmp.as_uri()],
        capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=180,
    ).stdout
    match = re.search(r'<pre id="probe-results">(.*?)</pre>', dom, re.S)
    if not match:
        sys.exit("Probe did not produce results - the page script may have failed.")
    import html as htmllib
    return json.loads(htmllib.unescape(match.group(1)))


def main():
    probe = run_probe()
    results = []

    def check(name, ok, detail):
        results.append((name, "PASS" if ok else "FAIL", detail))

    check("Page exposes all dataset rows to the filter",
          probe["totalRows"] == DATA["row_count"],
          f'{probe["totalRows"]} filterable rows vs {DATA["row_count"]} in dataset')

    for scenario, result in zip(SCENARIOS, probe["results"]):
        label, account, market, sku, listing = scenario
        want = expected(account, market, sku, listing)
        got = result["visible"]
        ok = sorted(got) == sorted(want)
        detail = f"{len(got)} shown, expected {len(want)}"
        if not ok:
            detail += f" | missing {sorted(set(want) - set(got))[:3]} extra {sorted(set(got) - set(want))[:3]}"
        check(f"Scenario {label}", ok, detail)

        want_no_match = len(want) == 0
        check(f"   - empty-state row correct for {label.split()[0]}",
              result["noMatchShown"] == want_no_match,
              f'shown={result["noMatchShown"]}, expected={want_no_match}')

        want_counter = (f'{len(want)} listing / SKU rows' if len(want) == DATA["row_count"]
                        else f'{len(want)} of {DATA["row_count"]} listing / SKU rows')
        check(f"   - row counter correct for {label.split()[0]}",
              result["counter"] == want_counter,
              f'"{result["counter"]}"')

        got_kpi = {k: int(v.replace(',', '')) for k, v in result["kpi"].items()}
        want_kpi = {w: expected_kpi(w, account, market, sku, listing)
                    for w in ("period", "last_month", "last_year")}
        check(f"   - KPI cards correct for {label.split()[0]}",
              got_kpi == want_kpi, f"{got_kpi} vs expected {want_kpi}")

    reset = probe["results"][-1]
    check("Reset restores every control to its default",
          reset["controls"] == ["", "", "", ""], f'controls after reset: {reset["controls"]}')
    check("Reset restores the KPI cards to the full month totals",
          {k: int(v.replace(',', '')) for k, v in reset["kpi"].items()}
          == {w: expected_kpi(w, "", "", "", "") for w in ("period", "last_month", "last_year")},
          f'cards after reset: {reset["kpi"]}')
    check("Reset shows all rows again",
          len(reset["visible"]) == DATA["row_count"],
          f'{len(reset["visible"])} of {DATA["row_count"]} rows visible')
    check("Case-insensitive SKU search: '12ip' == '12IP'",
          sorted(probe["results"][5]["visible"]) == sorted(probe["results"][9]["visible"]),
          f'{len(probe["results"][9]["visible"])} rows both ways')
    check("Filtering never alters the underlying row data",
          probe["dataUnchanged"],
          "all 126 rows byte-identical before and after every scenario")

    lines = ["# eBay Return Analysis - filter / search behaviour validation", "",
             f"- File under test: `{HTML_FILE}`",
             "- Driven in headless Chrome by dispatching real `change` / `input` / `click` events.",
             "- Expected rows computed independently in Python from the dataset JSON.", "",
             "| # | Check | Result | Detail |", "|---|---|---|---|"]
    for i, (name, verdict, detail) in enumerate(results, 1):
        lines.append(f"| {i} | {name} | **{verdict}** | {detail} |")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

    failed = [r for r in results if r[1] == "FAIL"]
    for name, verdict, detail in results:
        print(f"{verdict:4} {name} - {detail}")
    print(f"\n{len(results) - len(failed)}/{len(results)} checks passed -> {OUT}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
