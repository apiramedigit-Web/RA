"""Validate 04_Data/return_analysis_dataset.json against independent direct DB counts.

Read-only. Writes 05_Evidence/validation_report.md.
"""
import json
import os
import pathlib
from decimal import Decimal

import psycopg

BASE = pathlib.Path(__file__).resolve().parent.parent
DATA = json.loads((BASE / "04_Data" / "return_analysis_dataset.json").read_text(encoding="utf-8"))
ROWS = DATA["rows"]
COLUMNS = DATA["columns"]
OUT = BASE / "05_Evidence" / "validation_report.md"

P = ("2026-08-01", "2026-09-01")
LM = ("2026-07-01", "2026-08-01")
LY = ("2025-08-01", "2025-09-01")

results = []


def check(name, ok, detail):
    results.append((name, "PASS" if ok else "FAIL", detail))


def q(cur, sql, params=None):
    cur.execute(sql, params or ())
    return cur.fetchone()


def num(v):
    return 0 if v is None else v


dsn = os.environ.get("ERA_SOURCE_DB_URL") or os.environ["WLP_SOURCE_DB_URL"]
with psycopg.connect(dsn, connect_timeout=60) as conn:
    conn.read_only = True
    cur = conn.cursor()

    # --- 1. grain: no duplicate Listing ID + SKU rows -----------------------
    keys = [(r["Listing ID"], r["SKU"]) for r in ROWS]
    check("Grain unique (Listing ID + SKU)", len(keys) == len(set(keys)),
          f"{len(ROWS)} rows, {len(set(keys))} distinct keys")

    # --- 2. no fan-out on the return -> order line join ---------------------
    fan = q(cur, """
        SELECT COUNT(*) AS join_rows, COUNT(DISTINCT r.return_id) AS rets
        FROM customer_service.ebay_returns r
        JOIN order_management.order_item_info oi ON oi.item_transaction_id = r.transaction_id
        WHERE r.res_his_order = 0 AND r.request_date >= %s AND r.request_date < %s""", P)
    check("Return -> order line join is 1:1 (no fan-out)", fan[0] == fan[1],
          f"join rows {fan[0]} = distinct returns {fan[1]}")

    # --- 3. Returns reconcile to an independent direct count ----------------
    direct = q(cur, """
        SELECT COUNT(DISTINCT return_id) FROM customer_service.ebay_returns
        WHERE res_his_order = 0 AND request_date >= %s AND request_date < %s""", P)[0]
    report_returns = sum(r["Returns"] for r in ROWS)
    check("Returns total = direct DB count", report_returns == direct,
          f"report {report_returns} vs DB {direct}")

    # --- 4. Refund reconciles ----------------------------------------------
    direct_refund = q(cur, """
        SELECT ROUND(SUM(COALESCE(seller_refund_amount,0))::numeric, 2)
        FROM customer_service.ebay_returns
        WHERE res_his_order = 0 AND request_date >= %s AND request_date < %s""", P)[0]
    report_refund = round(sum(num(r["Refund (£)"]) for r in ROWS), 2)
    check("Refund total = direct DB sum", abs(report_refund - float(direct_refund)) < 0.02,
          f"report {report_refund} vs DB {direct_refund}")

    # --- 4b. Last Month Refund reconciles, row by row, to July returns ---------
    cur.execute("""
        SELECT r.item_id::text, COALESCE(NULLIF(oi.real_sku,''), oi.item_sku),
               ROUND(SUM(COALESCE(r.seller_refund_amount,0))::numeric, 2)
        FROM customer_service.ebay_returns r
        JOIN order_management.order_item_info oi ON oi.item_transaction_id = r.transaction_id
        WHERE r.res_his_order = 0 AND r.request_date >= %s AND r.request_date < %s
        GROUP BY 1, 2""", LM)
    lm_direct = {(l, s): float(v) for l, s, v in cur.fetchall()}
    lm_bad = [k for k in keys if abs(num(ROWS[keys.index(k)]["Last Month Refund (£)"]) - lm_direct.get(k, 0.0)) > 0.005]
    report_lm_refund = round(sum(num(r["Last Month Refund (£)"]) for r in ROWS), 2)
    direct_lm_refund = round(sum(lm_direct.get(k, 0.0) for k in keys), 2)
    check("Last Month Refund = direct July DB sum for the same Listing+SKU (every row)",
          not lm_bad and abs(report_lm_refund - direct_lm_refund) < 0.005,
          f"report {report_lm_refund} vs DB {direct_lm_refund}; {len(lm_bad)} mismatched rows")

    # --- 5. Open Cases reconcile -------------------------------------------
    direct_open = q(cur, """
        SELECT COUNT(DISTINCT return_id) FROM customer_service.ebay_returns
        WHERE res_his_order = 0 AND current_state <> 'CLOSED'
          AND request_date >= %s AND request_date < %s""", P)[0]
    report_open = sum(r["Open Cases"] for r in ROWS)
    check("Open Cases total = direct DB count", report_open == direct_open,
          f"report {report_open} vs DB {direct_open}")

    # --- 6. Return Cost reconciles -----------------------------------------
    direct_cost = q(cur, """
        SELECT ROUND(SUM(COALESCE(e.fee,0))::numeric, 2)
        FROM (SELECT DISTINCT transaction_id FROM customer_service.ebay_returns
              WHERE res_his_order = 0 AND request_date >= %s AND request_date < %s) t
        JOIN accounting.ebay_order_expenses e ON e.item_id::text = t.transaction_id
        WHERE e.transaction_type = 'REFUND'
          AND e.fee_type IN ('FINAL_VALUE_FEE','FINAL_VALUE_FEE_FIXED_PER_ORDER')""", P)[0]
    report_cost = round(sum(num(r["Return Cost (£)"]) for r in ROWS), 2)
    check("Return Cost total = direct DB sum", abs(report_cost - float(direct_cost)) < 0.02,
          f"report {report_cost} vs DB {direct_cost}")

    # --- 7. Negative Feedback reconciles ------------------------------------
    direct_neg = q(cur, """
        SELECT COUNT(*) FROM customer_service.ebay_orders_customer_feedbacks f
        JOIN order_management.order_item_info oi ON oi.item_transaction_id = f.transaction_id
        WHERE f.type = 'Negative' AND f.date >= %s AND f.date < %s""", P)[0]
    report_neg = sum(r["Negative Feedback"] for r in ROWS)
    check("Negative Feedback <= period total (rows are a subset of listings)",
          report_neg <= direct_neg,
          f"report {report_neg} of {direct_neg} negative feedbacks in period")

    # --- 8. Ad allocation never exceeds the listing's actual ad figures ------
    over = 0
    by_listing = {}
    for r in ROWS:
        k = r["Listing ID"]
        s, v = by_listing.get(k, (0.0, 0.0))
        by_listing[k] = (s + num(r["Ad Spend (£)"]), v + num(r["Ad Sales (£)"]))
    for lid, (spend, sales) in by_listing.items():
        row = q(cur, """
            SELECT ROUND(SUM(COALESCE(ad_fees_listing_currency,0))::numeric,2),
                   ROUND(SUM(COALESCE(sale_amount_listing_currency,0))::numeric,2)
            FROM ebay_campaigns.performance_data
            WHERE ebay_listing_id::text = %s AND date >= %s AND date < %s""", (lid,) + P)
        ls, lv = float(row[0] or 0), float(row[1] or 0)
        if spend > ls + 0.05 or sales > lv + 0.05:
            over += 1
    check("Allocated ad spend/sales never exceed the listing total (no double count)",
          over == 0, f"{over} of {len(by_listing)} listings over-allocated")

    # --- 8b. KPI window totals reconcile to direct per-month DB counts -------
    for key, (start, end) in [("period", P), ("last_month", LM), ("last_year", LY)]:
        direct_month = q(cur, """
            SELECT COUNT(DISTINCT return_id) FROM customer_service.ebay_returns
            WHERE res_his_order = 0 AND request_date >= %s AND request_date < %s""",
                         (start, end))[0]
        payload = sum(k["returns"] for k in DATA["kpi_windows"] if k["window_key"] == key)
        check(f"KPI window '{key}' = direct DB count for {start[:7]}",
              payload == direct_month, f"payload {payload} vs DB {direct_month}")

    # a filtered slice must reconcile too, not just the grand total
    slice_direct = q(cur, """
        SELECT COUNT(DISTINCT r.return_id) FROM customer_service.ebay_returns r
        JOIN order_management.sub_source ss ON ss.id = r.sub_source
        WHERE r.res_his_order = 0 AND ss.map_name = 'ledsone'
          AND r.request_date >= %s AND r.request_date < %s""", LY)[0]
    slice_payload = sum(k["returns"] for k in DATA["kpi_windows"]
                        if k["window_key"] == "last_year" and k["account"] == "ledsone")
    check("KPI filtered slice (ledsone, last year) = direct DB count",
          slice_payload == slice_direct, f"payload {slice_payload} vs DB {slice_direct}")

    # --- 9. Account / Market Place are unambiguous per report row -----------
    amb = q(cur, """
        SELECT COUNT(*) FROM (
          SELECT r.item_id::text lid, COALESCE(NULLIF(oi.real_sku,''), oi.item_sku) sku
          FROM customer_service.ebay_returns r
          JOIN order_management.order_item_info oi ON oi.item_transaction_id = r.transaction_id
          WHERE r.res_his_order = 0 AND r.request_date >= %s AND r.request_date < %s
          GROUP BY 1,2
          HAVING COUNT(DISTINCT r.sub_source) > 1 OR COUNT(DISTINCT r.market_place_code) > 1) x""", P)[0]
    check("Account / Market Place single-valued per Listing+SKU", amb == 0,
          f"{amb} rows with more than one account or marketplace")

# ---------------------------------------------------------------------------
# Formula checks - recomputed in Python from the row's own displayed inputs
# ---------------------------------------------------------------------------
def close(a, b, tol=0.011):
    return a is None and b is None or (a is not None and b is not None and abs(a - b) <= tol)


bad_rate = bad_acos = bad_roas = bad_rank = 0
for r in ROWS:
    if r["Total Orders"]:
        if not close(r["Return Rate"], round(r["Returns"] / r["Total Orders"] * 100, 2)):
            bad_rate += 1
    elif r["Return Rate"] is not None:
        bad_rate += 1
    spend, sales = r["Ad Spend (£)"], r["Ad Sales (£)"]
    if spend and sales:
        if not close(r["ACOS"], round(spend / sales * 100, 2), 0.06):
            bad_acos += 1
        if not close(r["ROAS"], round(sales / spend, 2), 0.06):
            bad_roas += 1

check("Return Rate = Returns / Total Orders x 100", bad_rate == 0, f"{bad_rate} mismatched rows")
check("ACOS = Ad Spend / Ad Sales x 100", bad_acos == 0, f"{bad_acos} mismatched rows")
check("ROAS = Ad Sales / Ad Spend", bad_roas == 0, f"{bad_roas} mismatched rows")

# Return Rank follows returns desc, then refund desc
ordered = sorted(ROWS, key=lambda r: (-r["Returns"], -num(r["Refund (£)"])))
prev_key, prev_rank = None, 0
for i, r in enumerate(ordered, 1):
    key = (r["Returns"], num(r["Refund (£)"]))
    expected = prev_rank if key == prev_key else i
    if r["Return Rank"] != expected:
        bad_rank += 1
    prev_key, prev_rank = key, expected
check("Return Rank = RANK() by Returns desc, Refund desc", bad_rank == 0, f"{bad_rank} mismatched rows")

# Main Return Reason comes from source values only
SOURCE_REASONS = {
    "ORDERED_WRONG_ITEM", "WRONG_SIZE", "NOT_AS_DESCRIBED", "ORDERED_ACCIDENTALLY",
    "DEFECTIVE_ITEM", "ARRIVED_DAMAGED", "NO_LONGER_NEED_ITEM",
    "ORDERED_DIFFERENT_ITEM", "MISSING_PARTS",
}
unknown = {r["Main Return Reason"] for r in ROWS} - SOURCE_REASONS
check("Main Return Reason values are raw source values", not unknown, f"unexpected: {sorted(unknown)}")

# Column set matches the requirement exactly
REQUIRED = [
    "Listing ID", "SKU", "Product Title", "Account", "Market Place", "Total Orders",
    "Returns", "Return Rate", "Last Month Returns", "Last Month Returns %",
    "Last Year Returns", "Last Year Returns %", "Refund (£)",
    "Last Month Refund (£)",  # business-approved addition (2026-09-17), not in the requirement PDF
    "Return Cost (£)",
    "Main Return Reason", "Return Rank", "Negative Feedback", "Open Cases", "Stock",
    "Ad Spend (£)", "Ad Sales (£)", "ACOS", "ROAS",
]
check("Column set = requirement + approved Last Month Refund, in order, nothing extra",
      COLUMNS == REQUIRED, f"{len(COLUMNS)} columns")

# Null profile of every required field
nulls = {c: sum(1 for r in ROWS if r[c] is None) for c in COLUMNS}
identity = ["Listing ID", "SKU", "Product Title", "Account", "Market Place",
            "Main Return Reason", "Return Rank", "Returns", "Total Orders"]
check("No null in identity / count fields", all(nulls[c] == 0 for c in identity),
      ", ".join(f"{c}={nulls[c]}" for c in identity))

lines = ["# eBay Return Analysis - validation report", "",
         f"- Source database: `{DATA['source_database']}` (read-only)",
         f"- Snapshot: {DATA['snapshot_utc']}",
         f"- Reporting period: {DATA['reporting_period']}",
         f"- Rows: {DATA['row_count']}", "",
         "## Checks", "", "| # | Check | Result | Detail |", "|---|---|---|---|"]
for i, (name, verdict, detail) in enumerate(results, 1):
    lines.append(f"| {i} | {name} | **{verdict}** | {detail} |")
lines += ["", "## Null counts per required column", "", "| Column | Nulls (of %d) |" % len(ROWS), "|---|---|"]
lines += [f"| {c} | {nulls[c]} |" for c in COLUMNS]
OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")

failed = [r for r in results if r[1] == "FAIL"]
for name, verdict, detail in results:
    print(f"{verdict:4} {name} - {detail}")
print(f"\n{len(results) - len(failed)}/{len(results)} checks passed -> {OUT}")
