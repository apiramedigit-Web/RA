"""Structured logging for the Return Analysis (RA) automation -- Step 11.

Writes a human-readable execution log, a separate error log and a machine
readable run summary. Never logs a credential.

The run summary always carries the fields the monthly requirement asks for:
execution date, calculated reporting month, Last Month period, Last Year
period, source row count, generated row count, validation result, publish
result and any errors.
"""
from __future__ import annotations

import datetime as dt
import json
import logging
import sys
import time
from typing import Any

import config


def _scrub(msg: str) -> str:
    """Belt-and-braces: never let a DSN reach a log file."""
    if "://" in msg and "@" in msg:
        parts = []
        for token in msg.split():
            if "://" in token and "@" in token:
                token = token.split("://")[0] + "://<redacted>"
            parts.append(token)
        return " ".join(parts)
    return msg


class RunLogger:
    def __init__(self, run_id: str, period=None) -> None:
        self.run_id = run_id
        self.period = period
        self.started = time.time()
        self.started_at = dt.datetime.now(config.TIMEZONE)
        self.errors: list[str] = []
        self.warnings: list[str] = []
        self.metrics: dict[str, Any] = {}
        self.stages: list[dict[str, Any]] = []
        self._stage_started: float | None = None
        self._stage_title: str | None = None

        fmt = logging.Formatter("%(asctime)s | %(levelname)-7s | %(message)s",
                                "%Y-%m-%d %H:%M:%S")
        self.log = logging.getLogger(f"ra.{run_id}")
        self.log.setLevel(logging.DEBUG)
        self.log.handlers.clear()
        self.log.propagate = False

        fh = logging.FileHandler(config.EXECUTION_LOG, encoding="utf-8")
        fh.setFormatter(fmt); fh.setLevel(logging.INFO)
        eh = logging.FileHandler(config.ERROR_LOG, encoding="utf-8")
        eh.setFormatter(fmt); eh.setLevel(logging.WARNING)
        sh = logging.StreamHandler(sys.stdout)
        sh.setFormatter(fmt); sh.setLevel(logging.INFO)
        for h in (fh, eh, sh):
            self.log.addHandler(h)

    # ---- messages --------------------------------------------------------
    def info(self, msg: str) -> None:
        self.log.info(_scrub(msg))

    def warn(self, msg: str) -> None:
        msg = _scrub(msg)
        self.warnings.append(msg)
        self.log.warning(msg)

    def error(self, msg: str) -> None:
        msg = _scrub(msg)
        self.errors.append(msg)
        self.log.error(msg)

    # ---- structure -------------------------------------------------------
    def stage(self, n: int, total: int, title: str) -> None:
        self._close_stage()
        self._stage_started = time.time()
        self._stage_title = title
        self.info(f"[{n}/{total}] {title}")

    def _close_stage(self) -> None:
        if self._stage_started is not None and self._stage_title:
            self.stages.append({
                "stage": self._stage_title,
                "seconds": round(time.time() - self._stage_started, 2),
            })
        self._stage_started = None
        self._stage_title = None

    def metric(self, key: str, value: Any) -> None:
        self.metrics[key] = value
        if isinstance(value, int) and not isinstance(value, bool):
            shown = f"{value:,}"
        else:
            shown = value
        self.info(f"   {key}: {shown}")

    # ---- completion ------------------------------------------------------
    def finish(self, status: str) -> dict[str, Any]:
        self._close_stage()
        ended_at = dt.datetime.now(config.TIMEZONE)
        p = self.period
        summary = {
            "run_id": self.run_id,
            "status": status,
            "start_time": self.started_at.strftime("%Y-%m-%d %H:%M:%S"),
            "end_time": ended_at.strftime("%Y-%m-%d %H:%M:%S"),
            "duration_seconds": round(time.time() - self.started, 2),
            # --- the mandated period fields -------------------------------
            "execution_date": p.execution_date.isoformat() if p else None,
            "reporting_month": p.month_key if p else None,
            "reporting_period": p.reporting_period if p else None,
            "last_month_period": p.last_month_period if p else None,
            "last_year_period": p.last_year_period if p else None,
            "sql_date_literals": p.sql_literals() if p else None,
            # --- counts / results -----------------------------------------
            "source_row_count": self.metrics.get("source_row_count"),
            "generated_row_count": self.metrics.get("generated_row_count"),
            "validation_result": self.metrics.get("validation_result"),
            "publish_result": self.metrics.get("publish_result"),
            "archive_result": self.metrics.get("archive_result"),
            "metrics": self.metrics,
            "stages": self.stages,
            "warnings": self.warnings,
            "errors": self.errors,
        }
        config.RUN_SUMMARY_JSON.write_text(
            json.dumps(summary, indent=2, default=str), encoding="utf-8")
        self.info(f"RUN {status} in {summary['duration_seconds']}s "
                  f"({len(self.warnings)} warning(s), {len(self.errors)} error(s))")
        for h in list(self.log.handlers):
            h.close()
            self.log.removeHandler(h)
        return summary

    def notify_failure(self, reason: str) -> None:
        if not config.NOTIFY_ON_FAILURE:
            return
        p = self.period
        config.FAILURE_NOTICE.write_text(
            f"Return Analysis (RA) automation FAILED\n"
            f"run id          : {self.run_id}\n"
            f"when            : {dt.datetime.now(config.TIMEZONE):%Y-%m-%d %H:%M:%S}\n"
            f"execution date  : {p.execution_date if p else '?'}\n"
            f"reporting month : {p.month_key if p else '?'}\n"
            f"reason          : {_scrub(reason)}\n\n"
            f"Nothing was published. The previous dashboard is unchanged:\n"
            f"  {config.LIVE_HTML}\n\n"
            f"See {config.ERROR_LOG} for the full trace.\n",
            encoding="utf-8")

    def clear_failure_notice(self) -> None:
        if config.FAILURE_NOTICE.exists():
            config.FAILURE_NOTICE.unlink()
