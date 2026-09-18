"""Step 5 -- Process Business Logic.

The approved Return Analysis business logic lives in
`02_SQL/ebay_return_analysis.sql` and is applied there, at source, unchanged.
This module does not recompute it and introduces no alternative calculation.

What it does is turn the query result into the report's row objects and then
re-derive the requirement's formulas from each row's OWN displayed inputs, so
that a silent change to the approved SQL cannot reach the dashboard unnoticed:

    Return Rate           = Returns / Total Orders x 100
    Last Month Returns %  = Last Month Returns / Last Month Orders x 100
    Last Year Returns %   = Last Year Returns  / Last Year Orders  x 100
    ACOS                  = Ad Spend / Ad Sales x 100
    ROAS                  = Ad Sales / Ad Spend
    Return Rank           = RANK() by Returns desc, Refund desc

(Last Month Orders and Last Year Orders are formula denominators only -- the
requirement does not list them as columns, so they are not displayed and the
two comparison percentages are re-derived from the SQL's own ratio instead.)
"""
from __future__ import annotations

import config


def _num(v):
    return 0 if v is None else v


def _close(a, b, tol) -> bool:
    if a is None and b is None:
        return True
    if a is None or b is None:
        return False
    return abs(a - b) <= tol


def run(raw: dict, period: config.Period, log) -> list[dict]:
    names = [config.ALIAS_TO_COLUMN[a] for a in raw["aliases"]]
    rows = [dict(zip(names, r)) for r in raw["rows"]]

    # --- requirement formulas, re-derived from each row's own inputs -------
    bad_rate = bad_acos = bad_roas = bad_rank = 0

    for r in rows:
        if r["Total Orders"]:
            if not _close(r["Return Rate"],
                          round(r["Returns"] / r["Total Orders"] * 100, 2),
                          config.RATE_TOLERANCE):
                bad_rate += 1
        elif r["Return Rate"] is not None:
            bad_rate += 1

        spend, sales = r["Ad Spend (£)"], r["Ad Sales (£)"]
        if spend and sales:
            if not _close(r["ACOS"], round(spend / sales * 100, 2), config.AD_TOLERANCE):
                bad_acos += 1
            if not _close(r["ROAS"], round(sales / spend, 2), config.AD_TOLERANCE):
                bad_roas += 1

    ordered = sorted(rows, key=lambda r: (-r["Returns"], -_num(r["Refund (£)"])))
    prev_key, prev_rank = None, 0
    for i, r in enumerate(ordered, 1):
        key = (r["Returns"], _num(r["Refund (£)"]))
        expected = prev_rank if key == prev_key else i
        if r["Return Rank"] != expected:
            bad_rank += 1
        prev_key, prev_rank = key, expected

    problems = []
    for label, n in (("Return Rate", bad_rate), ("ACOS", bad_acos),
                     ("ROAS", bad_roas), ("Return Rank", bad_rank)):
        if n:
            problems.append(f"{label}: {n} row(s) do not match the requirement formula")
    if problems:
        raise RuntimeError("business logic check failed -- " + "; ".join(problems))

    log.info("   PASS  Return Rate = Returns / Total Orders x 100")
    log.info("   PASS  ACOS = Ad Spend / Ad Sales x 100")
    log.info("   PASS  ROAS = Ad Sales / Ad Spend")
    log.info("   PASS  Return Rank = RANK() by Returns desc, Refund desc")

    # --- identity fields must never be empty -------------------------------
    identity = ["Listing ID", "SKU", "Product Title", "Account", "Market Place",
                "Main Return Reason", "Return Rank", "Returns", "Total Orders"]
    empty = {c: sum(1 for r in rows if r[c] is None) for c in identity}
    broken = {c: n for c, n in empty.items() if n}
    if broken:
        raise RuntimeError(f"identity/count fields contain nulls: {broken}")
    log.info("   PASS  no null in identity / count fields")

    totals = {
        "returns": sum(r["Returns"] for r in rows),
        "last_month_returns": sum(r["Last Month Returns"] for r in rows),
        "last_year_returns": sum(r["Last Year Returns"] for r in rows),
        "refund": round(sum(_num(r["Refund (£)"]) for r in rows), 2),
        "return_cost": round(sum(_num(r["Return Cost (£)"]) for r in rows), 2),
        "open_cases": sum(r["Open Cases"] for r in rows),
        "negative_feedback": sum(r["Negative Feedback"] for r in rows),
    }
    log.metric("period_returns", totals["returns"])
    log.metric("period_refund", f"{totals['refund']:,.2f}")
    log.metric("period_return_cost", f"{totals['return_cost']:,.2f}")

    return rows
