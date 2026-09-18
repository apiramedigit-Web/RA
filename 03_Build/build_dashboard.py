"""Render the validated dataset as a standalone eBay Return Analysis HTML report.

Reads 04_Data/return_analysis_dataset.json and writes 06_Output/eBay_Return_Analysis.html.
The output embeds every value it shows - no database, API or server at runtime.
"""
import html
import json
import pathlib

BASE = pathlib.Path(__file__).resolve().parent.parent
DATA_FILE = BASE / "04_Data" / "return_analysis_dataset.json"
OUT_FILE = BASE / "06_Output" / "eBay_Return_Analysis.html"

MONEY = {"Refund (£)", "Last Month Refund (£)", "Return Cost (£)", "Ad Spend (£)", "Ad Sales (£)"}
PERCENT = {"Return Rate", "Last Month Returns %", "Last Year Returns %", "ACOS"}
INTEGER = {"Total Orders", "Returns", "Last Month Returns", "Last Year Returns",
           "Negative Feedback", "Open Cases", "Stock"}
TEXT = {"Listing ID", "SKU", "Product Title", "Account", "Market Place", "Main Return Reason"}

# Business-requested display labels for Market Place. The dataset and the database
# keep the raw source code; only what the report shows and filters on is relabelled.
MARKET_PLACE_LABELS = {"EBAY_GB": "EBAY_UK"}


def cell(column, value):
    """Format one value; an absent value renders blank, never as a substitute number."""
    if value is None:
        return "", "num"
    if column in MONEY:
        return f"£{value:,.2f}", "num"
    if column in PERCENT:
        return f"{value:,.2f}%", "num"
    if column == "ROAS":
        return f"{value:,.2f}", "num"
    if column == "Return Rank":
        return f"#{value}", "num"
    if column in INTEGER:
        return f"{value:,.0f}", "num"
    return str(value), "txt"


def as_displayed(row):
    """The row exactly as the report shows it - only the Market Place label differs."""
    label = MARKET_PLACE_LABELS.get(row["Market Place"])
    return dict(row, **{"Market Place": label}) if label else row


def main():
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    columns = data["columns"]
    rows = [as_displayed(r) for r in data["rows"]]

    head = "".join(
        '<th class="{}{}" scope="col">{}</th>'.format(
            "txt" if c in TEXT else "num",
            f" col{i}" if i < 2 else "",
            html.escape(c),
        )
        for i, c in enumerate(columns)
    )

    body = []
    for row in rows:
        tds = []
        for i, c in enumerate(columns):
            text, kind = cell(c, row[c])
            sticky = f" col{i}" if i < 2 else ""
            title = f' title="{html.escape(text)}"' if c in ("SKU", "Product Title") else ""
            tds.append(f'<td class="{kind}{sticky}"{title}>{html.escape(text)}</td>')
        # Filter keys only - they duplicate the displayed values, never replace them.
        attrs = (
            f' data-account="{html.escape(row["Account"])}"'
            f' data-market="{html.escape(row["Market Place"])}"'
            f' data-sku="{html.escape(row["SKU"].lower())}"'
            f' data-listing="{html.escape(str(row["Listing ID"]).lower())}"'
        )
        body.append(f"<tr{attrs}>" + "".join(tds) + "</tr>")

    def options(column, all_label):
        opts = [f'<option value="">{html.escape(all_label)}</option>']
        opts += [
            f'<option value="{html.escape(v)}">{html.escape(v)}</option>'
            for v in sorted({r[column] for r in rows})
        ]
        return "".join(opts)

    account_options = options("Account", "(All Accounts)")
    market_options = options("Market Place", "(All Market Places)")

    # KPI card payload: returns per window at the grain the filters work on, so the
    # cards recompute for any filter combination. Same Returns metric as the table.
    kpi_data = json.dumps([
        {
            "w": k["window_key"],
            "l": str(k["listing_id"]).lower(),
            "s": (k["sku"] or "").lower(),
            "a": k["account"],
            "m": MARKET_PLACE_LABELS.get(k["market_place"], k["market_place"]),
            "n": k["returns"],
        }
        for k in data["kpi_windows"]
    ], separators=(",", ":"))

    kpi_cards = "".join(
        f'<div class="kpi"><span class="kpi-label">{html.escape(label)}</span>'
        f'<span class="kpi-period">{html.escape(period)}</span>'
        f'<span class="kpi-value" id="kpi-{key}">0</span>'
        f'<span class="kpi-unit">Returns</span></div>'
        for key, label, period in [
            ("period", "This Month", data["reporting_period"]),
            ("last_month", "Last Month", data["last_month_period"]),
            ("last_year", "Last Year", data["last_year_period"]),
        ]
    )

    doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>eBay Return Analysis</title>
<style>
  :root {{
    --bg: #f4f5f7;
    --surface: #ffffff;
    --border: #d8dce3;
    --border-soft: #e9ecf1;
    --text: #1d2430;
    --muted: #616c7d;
    --head: #eef1f5;
    --stripe: #fafbfc;
  }}
  @media (prefers-color-scheme: dark) {{
    :root:not([data-theme="light"]) {{
      --bg: #12151a; --surface: #1a1e25; --border: #333a45; --border-soft: #272d36;
      --text: #e6e9ee; --muted: #9aa5b4; --head: #222831; --stripe: #1d222a;
    }}
  }}
  :root[data-theme="dark"] {{
    --bg: #12151a; --surface: #1a1e25; --border: #333a45; --border-soft: #272d36;
    --text: #e6e9ee; --muted: #9aa5b4; --head: #222831; --stripe: #1d222a;
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px 16px 48px; background: var(--bg); color: var(--text);
    font: 14px/1.5 -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }}
  .wrap {{ max-width: 1600px; margin: 0 auto; }}
  h1 {{ margin: 0 0 6px; font-size: 22px; font-weight: 650; letter-spacing: -.01em; }}
  .meta {{ margin: 0 0 18px; color: var(--muted); font-size: 13px; }}
  .meta span {{ white-space: nowrap; }}
  .meta span + span::before {{ content: "·"; margin-right: 8px; opacity: .6; }}
  .controls {{
    display: flex; flex-wrap: wrap; align-items: flex-end; gap: 12px;
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 16px; margin: 0 0 14px;
  }}
  .controls label {{
    display: flex; flex-direction: column; gap: 5px;
    font-size: 12px; font-weight: 600; letter-spacing: .02em;
    text-transform: uppercase; color: var(--muted);
  }}
  .controls select, .controls input {{
    font: inherit; font-size: 14px; color: var(--text);
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 6px; padding: 7px 10px; min-width: 190px;
  }}
  .controls input::placeholder {{ color: var(--muted); opacity: .8; }}
  .controls select:focus-visible, .controls input:focus-visible,
  .controls button:focus-visible {{ outline: 2px solid #4a7fd4; outline-offset: 1px; }}
  .controls button {{
    font: inherit; font-size: 14px; color: var(--text); cursor: pointer;
    background: var(--head); border: 1px solid var(--border);
    border-radius: 6px; padding: 7px 16px;
  }}
  .controls button:hover {{ border-color: var(--muted); }}
  .kpis {{ display: flex; flex-wrap: wrap; gap: 12px; margin: 0 0 14px; }}
  .kpi {{
    flex: 1 1 190px; background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; padding: 14px 16px;
  }}
  .kpi-label {{
    display: block; font-size: 12px; font-weight: 600;
    letter-spacing: .02em; text-transform: uppercase; color: var(--muted);
  }}
  .kpi-period {{ display: block; margin-top: 2px; font-size: 12px; color: var(--muted); }}
  .kpi-value {{
    display: block; margin-top: 10px; font-size: 28px; font-weight: 650;
    line-height: 1.1; font-variant-numeric: tabular-nums;
  }}
  .kpi-unit {{ display: block; margin-top: 2px; font-size: 12px; color: var(--muted); }}
  .panel {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 10px; overflow: hidden;
  }}
  #no-match td {{ padding: 20px 16px; color: var(--muted); text-align: center; }}
  .scroll {{ overflow: auto; max-height: 76vh; }}
  table {{ border-collapse: separate; border-spacing: 0; width: 100%; font-variant-numeric: tabular-nums; }}
  th, td {{
    padding: 9px 12px; border-bottom: 1px solid var(--border-soft);
    white-space: nowrap; background: var(--surface);
  }}
  thead th {{
    position: sticky; top: 0; z-index: 3; background: var(--head);
    font-weight: 600; font-size: 12px; letter-spacing: .02em;
    text-transform: uppercase; color: var(--muted);
    border-bottom: 1px solid var(--border);
  }}
  th.num, td.num {{ text-align: right; }}
  th.txt, td.txt {{ text-align: left; }}
  tbody tr:nth-child(even) td {{ background: var(--stripe); }}
  tbody tr:hover td {{ background: var(--head); }}
  td.col0, th.col0 {{ position: sticky; left: 0; z-index: 2; }}
  td.col1, th.col1 {{ position: sticky; left: 116px; z-index: 2; }}
  thead th.col0, thead th.col1 {{ z-index: 4; }}
  td.col0, td.col1 {{ border-right: 1px solid var(--border-soft); }}
  td:nth-child(2) {{ max-width: 200px; overflow: hidden; text-overflow: ellipsis; }}
  td:nth-child(3) {{ max-width: 320px; overflow: hidden; text-overflow: ellipsis; }}
  tbody tr:last-child td {{ border-bottom: 0; }}
  @media (max-width: 720px) {{
    body {{ padding: 16px 16px 40px; }}
    h1 {{ font-size: 19px; }}
    .controls label {{ flex: 1 1 100%; }}
    .controls select, .controls input {{ min-width: 0; width: 100%; }}
    .controls button {{ flex: 1 1 100%; }}
    td.col1, th.col1 {{ position: static; }}
    td:nth-child(2) {{ max-width: 140px; }}
    td:nth-child(3) {{ max-width: 200px; }}
  }}
</style>
</head>
<body>
<div class="wrap">
  <h1>eBay Return Analysis</h1>
  <p class="meta">
    <span>Reporting period {html.escape(data["reporting_period"])}</span>
    <span>Last month {html.escape(data["last_month_period"])}</span>
    <span>Last year {html.escape(data["last_year_period"])}</span>
    <span id="row-count">{data["row_count"]} listing / SKU rows</span>
    <span>Source {html.escape(data["source_database"])}, snapshot {html.escape(data["snapshot_utc"])}</span>
  </p>
  <div class="controls">
    <label for="f-account">Account
      <select id="f-account">{account_options}</select>
    </label>
    <label for="f-market">Market Place
      <select id="f-market">{market_options}</select>
    </label>
    <label for="f-sku">SKU
      <input id="f-sku" type="search" placeholder="Search SKU" autocomplete="off">
    </label>
    <label for="f-listing">Listing ID
      <input id="f-listing" type="search" placeholder="Search Listing ID" autocomplete="off">
    </label>
    <button id="f-reset" type="button">Reset</button>
  </div>
  <div class="kpis">{kpi_cards}</div>
  <div class="panel">
    <div class="scroll">
      <table>
        <thead><tr>{head}</tr></thead>
        <tbody>
{chr(10).join(body)}
<tr id="no-match" hidden><td colspan="{len(columns)}">No rows match the current filters.</td></tr>
        </tbody>
      </table>
    </div>
  </div>
</div>
<script id="kpi-data" type="application/json">{kpi_data}</script>
<script>
// Show / hide existing rows, and total the KPI windows for the current filters.
// No business value is recalculated here - every number comes from the embedded data.
(function () {{
  var account = document.getElementById('f-account'),
      market  = document.getElementById('f-market'),
      sku     = document.getElementById('f-sku'),
      listing = document.getElementById('f-listing'),
      reset   = document.getElementById('f-reset'),
      noMatch = document.getElementById('no-match'),
      counter = document.getElementById('row-count'),
      rows    = Array.prototype.slice.call(
                  document.querySelectorAll('tbody tr:not(#no-match)')),
      total   = rows.length,
      kpiData = JSON.parse(document.getElementById('kpi-data').textContent),
      kpiEls  = {{
        period:     document.getElementById('kpi-period'),
        last_month: document.getElementById('kpi-last_month'),
        last_year:  document.getElementById('kpi-last_year')
      }};

  function kpiTotal(key, a, m, s, l) {{
    var sum = 0;
    kpiData.forEach(function (d) {{
      if (d.w !== key) {{ return; }}
      if (a !== '' && d.a !== a) {{ return; }}
      if (m !== '' && d.m !== m) {{ return; }}
      if (s !== '' && d.s.indexOf(s) === -1) {{ return; }}
      if (l !== '' && d.l.indexOf(l) === -1) {{ return; }}
      sum += d.n;
    }});
    return sum;
  }}

  function apply() {{
    var a = account.value,
        m = market.value,
        s = sku.value.trim().toLowerCase(),
        l = listing.value.trim().toLowerCase(),
        shown = 0;

    rows.forEach(function (row) {{
      var ok = (a === '' || row.getAttribute('data-account') === a)
            && (m === '' || row.getAttribute('data-market') === m)
            && (s === '' || row.getAttribute('data-sku').indexOf(s) !== -1)
            && (l === '' || row.getAttribute('data-listing').indexOf(l) !== -1);
      row.style.display = ok ? '' : 'none';
      if (ok) {{ shown++; }}
    }});

    noMatch.hidden = shown > 0;
    counter.textContent = (shown === total)
      ? total + ' listing / SKU rows'
      : shown + ' of ' + total + ' listing / SKU rows';

    Object.keys(kpiEls).forEach(function (key) {{
      kpiEls[key].textContent = kpiTotal(key, a, m, s, l).toLocaleString('en-GB');
    }});
  }}

  [account, market].forEach(function (el) {{ el.addEventListener('change', apply); }});
  [sku, listing].forEach(function (el) {{ el.addEventListener('input', apply); }});
  reset.addEventListener('click', function () {{
    account.value = ''; market.value = ''; sku.value = ''; listing.value = '';
    apply();
  }});
  apply();
}})();
</script>
</body>
</html>
"""
    OUT_FILE.write_text(doc, encoding="utf-8")
    print(f"{len(rows)} rows -> {OUT_FILE} ({OUT_FILE.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
