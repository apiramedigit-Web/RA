"""Step 4 -- Validate Source Data.

Runs BEFORE any report is generated. Checks that the source is present,
complete enough to report on, and free of the structural faults that would
silently corrupt the figures: missing data, duplicate returns, duplicate
joins / fan-out, and Listing ID / SKU / Account / Marketplace mapping gaps.

All queries are read-only and hit the source tables directly -- none of them
reuses the report SQL.

A hard failure raises and stops the run before anything is generated.
Soft findings are logged as warnings and carried into the evidence file; the
known, already-documented source gaps (05_Evidence/04_gaps_and_limits.md)
are reported as facts, never patched with an invented value.
"""
from __future__ import annotations

import psycopg

import config

HARD = "ERROR"
SOFT = "WARN"


def _table_exists(cur, qualified: str) -> bool:
    schema, table = qualified.split(".", 1)
    cur.execute(
        "SELECT 1 FROM information_schema.tables WHERE table_schema=%s AND table_name=%s",
        (schema, table))
    return cur.fetchone() is not None


def run(raw: dict, period: config.Period, log) -> dict:
    lits = period.sql_literals()
    P = (lits["p_start"], lits["p_end"])
    LM = (lits["lm_start"], lits["lm_end"])
    LY = (lits["ly_start"], lits["ly_end"])

    findings: list[tuple[str, str, str]] = []      # (severity, check, detail)
    facts: dict[str, object] = {}

    def ok(check: str, detail: str = "") -> None:
        log.info(f"   PASS  {check}{(' - ' + detail) if detail else ''}")

    def fail(severity: str, check: str, detail: str) -> None:
        findings.append((severity, check, detail))
        (log.error if severity == HARD else log.warn)(f"   {severity}  {check} - {detail}")

    # --- A. the fetched result must match the report contract --------------
    aliases = raw["aliases"]
    unexpected = [a for a in aliases if a not in config.ALIAS_TO_COLUMN]
    if unexpected:
        fail(HARD, "Query returns only the approved columns",
             f"unexpected columns: {unexpected}")
    else:
        names = [config.ALIAS_TO_COLUMN[a] for a in aliases]
        if names != list(config.COLUMNS):
            fail(HARD, "Column set and order match the requirement",
                 f"got {names}")
        else:
            ok("Column set and order match the requirement",
               f"{len(names)} columns")

    if len(raw["rows"]) < config.MIN_REPORT_ROWS:
        fail(HARD, "Source produced a reportable number of rows",
             f"{len(raw['rows'])} rows, minimum {config.MIN_REPORT_ROWS}")
    else:
        ok("Source produced a reportable number of rows", f"{len(raw['rows'])} rows")

    with psycopg.connect(config.source_db_url(),
                         connect_timeout=config.DB_CONNECT_TIMEOUT) as conn:
        conn.read_only = True
        cur = conn.cursor()
        cur.execute(f"SET statement_timeout = {config.DB_STATEMENT_TIMEOUT_MS}")

        # --- B. every source table the approved SQL reads is present -------
        missing_tables = [t for t in config.REQUIRED_SOURCE_TABLES
                          if not _table_exists(cur, t)]
        if missing_tables:
            fail(HARD, "All required source tables exist", f"missing: {missing_tables}")
        else:
            ok("All required source tables exist",
               f"{len(config.REQUIRED_SOURCE_TABLES)} tables")

        # --- C. each window actually holds data ----------------------------
        for label, window in (("reporting", P), ("last month", LM), ("last year", LY)):
            cur.execute(
                "SELECT COUNT(DISTINCT return_id) FROM customer_service.ebay_returns "
                "WHERE res_his_order = 0 AND request_date >= %s AND request_date < %s",
                window)
            n = cur.fetchone()[0]
            facts[f"returns_{label.replace(' ', '_')}"] = n
            if label == "reporting" and n < config.MIN_PERIOD_RETURNS:
                fail(HARD, f"{label} window has returns",
                     f"{n} returns in {window[0]}..{window[1]}, "
                     f"minimum {config.MIN_PERIOD_RETURNS}")
            elif n == 0:
                fail(SOFT, f"{label} window has returns",
                     f"0 returns in {window[0]}..{window[1]} - the comparison "
                     "column will legitimately be 0 for every row")
            else:
                ok(f"{label} window has returns", f"{n} returns")

        # --- D. duplicate returns in the current-row population ------------
        cur.execute(
            "SELECT COUNT(*), COUNT(DISTINCT return_id) "
            "FROM customer_service.ebay_returns "
            "WHERE res_his_order = 0 AND request_date >= %s AND request_date < %s", P)
        rows_n, distinct_n = cur.fetchone()
        if rows_n != distinct_n:
            fail(HARD, "No duplicate return rows (res_his_order = 0 is one row per return)",
                 f"{rows_n} rows for {distinct_n} distinct return_id")
        else:
            ok("No duplicate return rows", f"{distinct_n} returns, one row each")

        # --- E. return -> order line join is 1:1 in every window ------------
        for label, window in (("reporting", P), ("last month", LM), ("last year", LY)):
            cur.execute(
                "SELECT COUNT(*), COUNT(DISTINCT r.return_id) "
                "FROM customer_service.ebay_returns r "
                "JOIN order_management.order_item_info oi "
                "  ON oi.item_transaction_id = r.transaction_id "
                "WHERE r.res_his_order = 0 AND r.request_date >= %s AND r.request_date < %s",
                window)
            join_rows, rets = cur.fetchone()
            if join_rows != rets:
                fail(HARD, f"No join fan-out on the {label} window",
                     f"{join_rows} joined rows for {rets} returns")
            else:
                ok(f"No join fan-out on the {label} window", f"{join_rows} = {rets}")

        # --- F. orphan returns: no matching order line ----------------------
        cur.execute(
            "SELECT COUNT(DISTINCT r.return_id) FROM customer_service.ebay_returns r "
            "LEFT JOIN order_management.order_item_info oi "
            "  ON oi.item_transaction_id = r.transaction_id "
            "WHERE r.res_his_order = 0 AND r.request_date >= %s AND r.request_date < %s "
            "  AND oi.item_transaction_id IS NULL", P)
        orphans = cur.fetchone()[0]
        facts["orphan_returns"] = orphans
        total_period = facts["returns_reporting"]
        if orphans:
            fail(SOFT, "Every reporting-period return resolves to an order line "
                       "(Listing ID + SKU mapping)",
                 f"{orphans} of {total_period} returns have no order line and are "
                 "therefore absent from the report")
        else:
            ok("Every reporting-period return resolves to an order line",
               f"{total_period} returns mapped")

        # --- G. Account / Market Place mapping ------------------------------
        cur.execute(
            "SELECT COUNT(DISTINCT r.return_id) FILTER (WHERE ss.map_name IS NULL), "
            "       COUNT(DISTINCT r.return_id) FILTER (WHERE r.market_place_code IS NULL), "
            "       COUNT(DISTINCT r.return_id) "
            "FROM customer_service.ebay_returns r "
            "JOIN order_management.order_item_info oi "
            "  ON oi.item_transaction_id = r.transaction_id "
            "LEFT JOIN order_management.sub_source ss ON ss.id = r.sub_source "
            "WHERE r.res_his_order = 0 AND r.request_date >= %s AND r.request_date < %s", P)
        no_account, no_market, mapped = cur.fetchone()
        facts["returns_without_account"] = no_account
        facts["returns_without_marketplace"] = no_market
        pct = (no_account / mapped * 100) if mapped else 0.0
        if pct > config.MAX_MISSING_ACCOUNT_PCT:
            fail(HARD, "Account mapping is complete enough to report",
                 f"{no_account} of {mapped} returns ({pct:.1f}%) have no sub_source "
                 f"mapping, limit {config.MAX_MISSING_ACCOUNT_PCT}%")
        elif no_account or no_market:
            fail(SOFT, "Account / Market Place mapping complete",
                 f"{no_account} returns without an account, "
                 f"{no_market} without a marketplace code")
        else:
            ok("Account / Market Place mapping complete", f"{mapped} returns")

        # --- H. Account / Market Place single-valued per Listing + SKU ------
        cur.execute(
            "SELECT COUNT(*) FROM ("
            "  SELECT r.item_id, COALESCE(NULLIF(oi.real_sku,''), oi.item_sku) sku "
            "  FROM customer_service.ebay_returns r "
            "  JOIN order_management.order_item_info oi "
            "    ON oi.item_transaction_id = r.transaction_id "
            "  WHERE r.res_his_order = 0 AND r.request_date >= %s AND r.request_date < %s "
            "  GROUP BY 1,2 "
            "  HAVING COUNT(DISTINCT r.sub_source) > 1 "
            "      OR COUNT(DISTINCT r.market_place_code) > 1) x", P)
        ambiguous = cur.fetchone()[0]
        facts["ambiguous_listing_sku"] = ambiguous
        if ambiguous:
            fail(SOFT, "Account / Market Place single-valued per Listing ID + SKU",
                 f"{ambiguous} Listing+SKU keys carry more than one account or "
                 "marketplace; the report shows the most frequent value")
        else:
            ok("Account / Market Place single-valued per Listing ID + SKU")

        # --- I. required return fields populated ----------------------------
        cur.execute(
            "SELECT COUNT(*) FILTER (WHERE r.item_id IS NULL), "
            "       COUNT(*) FILTER (WHERE r.reason IS NULL OR r.reason = ''), "
            "       COUNT(*) FILTER (WHERE r.current_state IS NULL), "
            "       COUNT(*) FILTER (WHERE COALESCE(NULLIF(oi.real_sku,''), oi.item_sku) IS NULL) "
            "FROM customer_service.ebay_returns r "
            "JOIN order_management.order_item_info oi "
            "  ON oi.item_transaction_id = r.transaction_id "
            "WHERE r.res_his_order = 0 AND r.request_date >= %s AND r.request_date < %s", P)
        null_listing, null_reason, null_state, null_sku = cur.fetchone()
        required_nulls = {"item_id": null_listing, "reason": null_reason,
                          "current_state": null_state, "sku": null_sku}
        facts["required_field_nulls"] = required_nulls
        broken = {k: v for k, v in required_nulls.items() if v}
        if broken:
            fail(HARD, "Required return fields are populated", f"nulls: {broken}")
        else:
            ok("Required return fields are populated",
               "item_id, reason, current_state, sku")

        # --- J. new return reasons the build has not seen before ------------
        cur.execute(
            "SELECT DISTINCT reason FROM customer_service.ebay_returns "
            "WHERE res_his_order = 0 AND request_date >= %s AND request_date < %s", P)
        reasons = {r[0] for r in cur.fetchall() if r[0]}
        new_reasons = sorted(reasons - config.KNOWN_RETURN_REASONS)
        facts["return_reasons"] = sorted(reasons)
        if new_reasons:
            fail(SOFT, "Return reasons are known source values",
                 f"new source value(s): {new_reasons} - shown verbatim, not remapped")
        else:
            ok("Return reasons are known source values", f"{len(reasons)} distinct")

        # --- K. supporting sources present for the reporting month ----------
        cur.execute(
            "SELECT COUNT(*) FROM ebay_campaigns.performance_data "
            "WHERE date >= %s AND date < %s", P)
        ad_rows = cur.fetchone()[0]
        facts["ad_performance_rows"] = ad_rows
        if ad_rows == 0:
            fail(SOFT, "Advertising data present for the reporting month",
                 "0 rows in ebay_campaigns.performance_data - Ad Spend, Ad Sales, "
                 "ACOS and ROAS will be 0 / blank for every row")
        else:
            ok("Advertising data present for the reporting month", f"{ad_rows} rows")

        cur.execute("SELECT COUNT(*) FROM inventory.local_inventory_current_stock_location_wise")
        stock_rows = cur.fetchone()[0]
        facts["stock_rows"] = stock_rows
        if stock_rows == 0:
            fail(HARD, "Live stock source is populated", "0 rows")
        else:
            ok("Live stock source is populated", f"{stock_rows} location rows")

    # --- L. duplicate Listing ID + SKU in the fetched result ---------------
    li = raw["aliases"].index("Listing ID")
    sk = raw["aliases"].index("SKU")
    keys = [(r[li], r[sk]) for r in raw["rows"]]
    if len(keys) != len(set(keys)):
        dupes = sorted({k for k in keys if keys.count(k) > 1})[:5]
        fail(HARD, "No duplicate Listing ID + SKU rows in the fetched result",
             f"{len(keys) - len(set(keys))} duplicates, e.g. {dupes}")
    else:
        ok("No duplicate Listing ID + SKU rows in the fetched result",
           f"{len(keys)} unique keys")

    hard = [f for f in findings if f[0] == HARD]
    soft = [f for f in findings if f[0] == SOFT]
    log.metric("source_validation",
               f"{len(hard)} error(s), {len(soft)} warning(s)")

    _write_evidence(period, facts, findings, log)

    if hard:
        raise RuntimeError(
            "source data validation failed: "
            + "; ".join(f"{c} ({d})" for _, c, d in hard))

    return {"facts": facts, "findings": findings}


def _write_evidence(period, facts, findings, log) -> None:
    lines = [
        "# Return Analysis - source data validation (Step 4)", "",
        f"- Execution date: {period.execution_date}",
        f"- Reporting month: **{period.month_label}** ({period.reporting_period})",
        f"- Last Month: {period.last_month_label} ({period.last_month_period})",
        f"- Last Year: {period.last_year_label} ({period.last_year_period})",
        f"- Source database: `{config.SOURCE_DB_NAME}` (read-only)", "",
        "## Findings", "",
    ]
    if findings:
        lines += ["| Severity | Check | Detail |", "|---|---|---|"]
        lines += [f"| **{s}** | {c} | {d} |" for s, c, d in findings]
    else:
        lines.append("No findings - every source check passed.")
    lines += ["", "## Facts", "", "| Fact | Value |", "|---|---|"]
    lines += [f"| {k} | {v} |" for k, v in facts.items()]
    config.AUTOMATION_SOURCE_MD.write_text("\n".join(lines) + "\n", encoding="utf-8")
    log.info(f"   evidence -> {config.AUTOMATION_SOURCE_MD.name}")
