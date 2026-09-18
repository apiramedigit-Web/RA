"""Step 3 -- Fetch Data.

Runs the APPROVED Return Analysis SQL against `ledsone`, read-only.

The two query files in `02_SQL/` are the source of truth for the business
logic and are reused byte-for-byte, with one exception: the six date literals
in their `params` CTE are replaced with the dates this run calculated. Nothing
else in either file is touched, and that is enforced -- `render_sql()` proves
the rendered text differs from the original only in those six literals by
re-rendering with the file's own dates and demanding the original back.

Reads only. No write, no DDL, no temporary table is ever issued.
"""
from __future__ import annotations

import datetime as dt
import decimal
import re
from pathlib import Path

import psycopg

import config

# DATE 'yyyy-mm-dd' AS <one of the six params>
_LITERAL = re.compile(
    r"(DATE\s+')(\d{4}-\d{2}-\d{2})('\s+AS\s+(p_start|p_end|lm_start|lm_end|ly_start|ly_end)\b)",
    re.IGNORECASE,
)
PARAM_NAMES = ("p_start", "p_end", "lm_start", "lm_end", "ly_start", "ly_end")


def _substitute(sql: str, literals: dict[str, str]) -> tuple[str, dict[str, str]]:
    """Replace the six params-CTE date literals. Returns (sql, dates_found)."""
    found: dict[str, str] = {}

    def repl(m: re.Match) -> str:
        name = m.group(4).lower()
        found[name] = m.group(2)
        return f"{m.group(1)}{literals[name]}{m.group(3)}"

    return _LITERAL.sub(repl, sql), found


def render_sql(path: Path, period: config.Period) -> str:
    """The approved query with this run's dates, and only its dates, substituted."""
    original = path.read_text(encoding="utf-8")

    rendered, original_dates = _substitute(original, period.sql_literals())

    missing = [n for n in PARAM_NAMES if n not in original_dates]
    if missing:
        raise RuntimeError(
            f"{path.name}: the params CTE does not define {missing}. The approved "
            "query shape changed -- the automation will not guess at it.")
    if len(original_dates) != len(PARAM_NAMES):
        raise RuntimeError(
            f"{path.name}: expected exactly {len(PARAM_NAMES)} date literals, "
            f"found {len(original_dates)}")

    # Proof that nothing but the six literals moved: putting the file's own
    # dates back must reproduce the file exactly, byte for byte.
    round_trip, _ = _substitute(rendered, original_dates)
    if round_trip != original:
        raise RuntimeError(
            f"{path.name}: rendering changed more than the six date literals. "
            "Refusing to run -- the approved business logic must not be altered.")

    return rendered


def _jsonable(value):
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    return value


def fetch(period: config.Period, log) -> dict:
    """Run both approved queries and return their raw results."""
    dataset_sql = render_sql(config.SQL_DATASET, period)
    kpi_sql = render_sql(config.SQL_KPI_WINDOWS, period)

    lits = period.sql_literals()
    log.info(f"   reporting window   : {lits['p_start']} <= request_date < {lits['p_end']}")
    log.info(f"   last month window  : {lits['lm_start']} <= request_date < {lits['lm_end']}")
    log.info(f"   last year window   : {lits['ly_start']} <= request_date < {lits['ly_end']}")
    log.info(f"   SQL                : {config.SQL_DATASET.name} + "
             f"{config.SQL_KPI_WINDOWS.name} (approved, dates substituted only)")

    with psycopg.connect(config.source_db_url(),
                         connect_timeout=config.DB_CONNECT_TIMEOUT) as conn:
        conn.read_only = True
        with conn.cursor() as cur:
            cur.execute(f"SET statement_timeout = {config.DB_STATEMENT_TIMEOUT_MS}")
            cur.execute("SELECT current_database(), now()")
            database, snapshot = cur.fetchone()

            cur.execute(dataset_sql)
            aliases = [d[0] for d in cur.description]
            raw_rows = [[_jsonable(v) for v in r] for r in cur.fetchall()]

            cur.execute(kpi_sql)
            kpi_cols = [d[0] for d in cur.description]
            kpi_rows = [dict(zip(kpi_cols, (_jsonable(v) for v in r)))
                        for r in cur.fetchall()]

    log.metric("source_database", database)
    log.metric("source_snapshot_utc",
               snapshot.astimezone(dt.timezone.utc).isoformat(timespec="seconds"))
    log.metric("source_row_count", len(raw_rows))
    log.metric("source_kpi_rows", len(kpi_rows))

    return {
        "database": database,
        "snapshot_utc": snapshot.astimezone(dt.timezone.utc).isoformat(timespec="seconds"),
        "aliases": aliases,
        "rows": raw_rows,
        "kpi_rows": kpi_rows,
        "rendered_sql": {config.SQL_DATASET.name: dataset_sql,
                         config.SQL_KPI_WINDOWS.name: kpi_sql},
    }
