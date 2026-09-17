"""Run ebay_return_analysis.sql against ledsone and save the validated dataset.

Read-only. Writes 04_Data/return_analysis_dataset.json only.
"""
import datetime as dt
import decimal
import json
import os
import pathlib
import sys

import psycopg

BASE = pathlib.Path(__file__).resolve().parent.parent
SQL_FILE = BASE / "02_SQL" / "ebay_return_analysis.sql"
KPI_SQL_FILE = BASE / "02_SQL" / "return_kpi_windows.sql"
OUT_FILE = BASE / "04_Data" / "return_analysis_dataset.json"

COLUMNS = [
    "Listing ID", "SKU", "Product Title", "Account", "Market Place",
    "Total Orders", "Returns", "Return Rate",
    "Last Month Returns", "Last Month Returns %",
    "Last Year Returns", "Last Year Returns %",
    "Refund (£)", "Return Cost (£)", "Main Return Reason", "Return Rank",
    "Negative Feedback", "Open Cases", "Stock",
    "Ad Spend (£)", "Ad Sales (£)", "ACOS", "ROAS",
]
# SQL aliases carry no currency symbol; map them onto the required column names.
ALIAS_TO_COLUMN = {c.replace(" (£)", ""): c for c in COLUMNS}


def jsonable(value):
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def main():
    dsn = os.environ.get("ERA_SOURCE_DB_URL") or os.environ["WLP_SOURCE_DB_URL"]
    sql = SQL_FILE.read_text(encoding="utf-8")

    with psycopg.connect(dsn, connect_timeout=60) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute("SELECT current_database(), now()")
            database, snapshot = cur.fetchone()
            cur.execute(sql)
            aliases = [d[0] for d in cur.description]
            raw_rows = cur.fetchall()
            cur.execute(KPI_SQL_FILE.read_text(encoding="utf-8"))
            kpi_cols = [d[0] for d in cur.description]
            kpi_rows = [dict(zip(kpi_cols, r)) for r in cur.fetchall()]

    missing = [a for a in aliases if a not in ALIAS_TO_COLUMN]
    if missing:
        sys.exit(f"Query returned unexpected columns: {missing}")
    names = [ALIAS_TO_COLUMN[a] for a in aliases]
    if names != COLUMNS:
        sys.exit(f"Column order does not match the requirement.\n got: {names}\nwant: {COLUMNS}")

    rows = [{n: jsonable(v) for n, v in zip(names, r)} for r in raw_rows]

    payload = {
        "report": "eBay Return Analysis",
        "requirement": "System Task - Return Analysis - kobiga.pdf",
        "source_database": database,
        "snapshot_utc": snapshot.astimezone(dt.timezone.utc).isoformat(timespec="seconds"),
        "reporting_period": "2026-08-01 to 2026-08-31",
        "last_month_period": "2026-07-01 to 2026-07-31",
        "last_year_period": "2025-08-01 to 2025-08-31",
        "columns": COLUMNS,
        "row_count": len(rows),
        "rows": rows,
        # Returns per window at the grain the report filters on - feeds the KPI cards.
        "kpi_windows": kpi_rows,
    }
    OUT_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"rows={len(rows)} -> {OUT_FILE}")


if __name__ == "__main__":
    main()
