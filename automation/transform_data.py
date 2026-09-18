"""Step 6 -- Transform Data.

Assembles the report rows and the KPI windows into the dataset payload the
approved renderer (`03_Build/build_dashboard.py`) consumes.

The payload shape is exactly the one `03_Build/extract_dataset.py` produces --
same keys, same column order, same KPI window records. The only difference is
that the three period strings are the ones this run calculated instead of
literals typed into a file.

Written to the staging area only. Nothing under 04_Data/ or 06_Output/ is
touched until the output has been validated.
"""
from __future__ import annotations

import json

import config


def run(rows: list[dict], raw: dict, period: config.Period, log) -> dict:
    payload = {
        "report": config.REPORT_TITLE,
        "requirement": config.REQUIREMENT,
        "source_database": raw["database"],
        "snapshot_utc": raw["snapshot_utc"],
        "reporting_period": period.reporting_period,
        "last_month_period": period.last_month_period,
        "last_year_period": period.last_year_period,
        "columns": list(config.COLUMNS),
        "row_count": len(rows),
        "rows": rows,
        # Returns per window at the grain the report filters on - feeds the KPI cards.
        "kpi_windows": raw["kpi_rows"],
    }

    config.STAGING_DATASET.write_text(
        json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    kpi = {w: sum(k["returns"] for k in payload["kpi_windows"] if k["window_key"] == w)
           for w in config.KPI_WINDOWS}
    log.metric("generated_row_count", payload["row_count"])
    log.metric("kpi_this_month", kpi["period"])
    log.metric("kpi_last_month", kpi["last_month"])
    log.metric("kpi_last_year", kpi["last_year"])
    log.info(f"   staged dataset -> {config.STAGING_DATASET.name} "
             f"({config.STAGING_DATASET.stat().st_size:,} bytes)")

    return payload
