"""eBay Return Analysis (RA) -- monthly automation entry point.

    python run.py                          full monthly run
    python run.py --dry-run                everything except publish and archive
    python run.py --as-of 2026-10-01       simulate a run on that date
    python run.py --dates-only             print the calculated periods, touch nothing
    python run.py --preflight              environment readiness check only
    python run.py --compare-with <file>    dry run, then diff against a known dataset

The Windows scheduled task calls exactly this file with no arguments, so a
manual run and the 1st-of-the-month run execute identical code.

Workflow (Common Automation Workflow)
-------------------------------------
    Scheduler -> Configuration -> Fetch Data -> Validate Source Data
    -> Process Business Logic -> Transform Data -> Generate Output
    -> Validate Output -> Publish / Store Output -> Archive -> Logging

Reporting period
----------------
Calculated from the execution date, never hardcoded: the reporting period is
always the previous calendar month, Last Month the month before that, and Last
Year the same calendar month a year earlier. All windows are half-open:
start <= request_date < end, on the approved `request_date` basis.

Failure handling
----------------
Any failing stage stops the run before the publish stage. The live report is
only ever replaced by an atomic swap of a validated staging file, so a failed
run leaves the previous known-good report and the published task cards exactly
as they were.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
import traceback

import config
import logger as logger_mod

TOTAL_STEPS = 11


def preflight(log, need_db: bool = True) -> list[str]:
    problems: list[str] = []

    if need_db:
        if not config.source_db_available():
            problems.append(
                f"none of {' / '.join(config.SOURCE_DB_ENVS)} is set -- "
                f"{config.SOURCE_DB_NAME} is unreachable")
        if not config.publish_db_available():
            problems.append(
                f"${config.PUBLISH_DB_ENV} is not set -- the approved publisher "
                f"cannot reach {config.PUBLISH_DB_NAME}")

    for path in (config.SQL_DATASET, config.SQL_KPI_WINDOWS,
                 config.BUILDER_MODULE, config.PUBLISHER_MODULE):
        if not path.exists():
            problems.append(f"missing approved artefact: {path}")

    try:
        import psycopg  # noqa: F401
    except ImportError:
        problems.append("psycopg is not installed (pip install -r requirements.txt)")

    if len(config.COLUMNS) != 24:
        problems.append(f"config.COLUMNS must define 24 columns, has {len(config.COLUMNS)}")

    for p in problems:
        log.error(f"   PREFLIGHT: {p}")
    if not problems:
        log.info("   preflight: PASS")
    return problems


def log_period(log, period: config.Period) -> None:
    log.metric("execution_date", period.execution_date.isoformat())
    log.metric("reporting_month", f"{period.month_key} ({period.month_label})")
    log.metric("reporting_period", period.reporting_period)
    log.metric("last_month_period",
               f"{period.last_month_period} ({period.last_month_label})")
    log.metric("last_year_period",
               f"{period.last_year_period} ({period.last_year_label})")
    lits = period.sql_literals()
    log.info(f"   half-open windows: "
             f"[{lits['p_start']}, {lits['p_end']}) "
             f"[{lits['lm_start']}, {lits['lm_end']}) "
             f"[{lits['ly_start']}, {lits['ly_end']})")


def compare_with(reference: str, payload: dict, log) -> bool:
    """Diff the generated dataset against a known-good one, cell by cell."""
    from pathlib import Path
    ref = json.loads(Path(reference).read_text(encoding="utf-8"))

    log.info(f"   reference: {reference}")
    same = True

    for field in ("reporting_period", "last_month_period", "last_year_period",
                  "columns", "row_count"):
        if ref.get(field) != payload.get(field):
            log.error(f"   DIFF {field}: reference {ref.get(field)!r} "
                      f"vs generated {payload.get(field)!r}")
            same = False
        else:
            log.info(f"   same {field}: {payload.get(field)!r}"[:160])

    ref_rows = {(r["Listing ID"], r["SKU"]): r for r in ref["rows"]}
    gen_rows = {(r["Listing ID"], r["SKU"]): r for r in payload["rows"]}

    only_ref = sorted(ref_rows.keys() - gen_rows.keys())
    only_gen = sorted(gen_rows.keys() - ref_rows.keys())
    if only_ref or only_gen:
        log.error(f"   DIFF row keys: {len(only_ref)} only in reference "
                  f"{only_ref[:3]}, {len(only_gen)} only in generated {only_gen[:3]}")
        same = False

    # Stock and Open Cases are read live and cannot be restated for a past
    # month, so a difference in them is source movement, not a report change.
    # They are reported separately and never hidden.
    locked_diffs, live_diffs = [], []
    for key in sorted(ref_rows.keys() & gen_rows.keys()):
        for column in payload["columns"]:
            a, b = ref_rows[key].get(column), gen_rows[key].get(column)
            if isinstance(a, float) or isinstance(b, float):
                if a is None or b is None:
                    equal = a == b
                else:
                    equal = abs(float(a) - float(b)) < 0.005
            else:
                equal = a == b
            if not equal:
                diff = f"{key[0]}/{key[1]}/{column}: {a!r} != {b!r}"
                (live_diffs if column in config.LIVE_SNAPSHOT_COLUMNS
                 else locked_diffs).append(diff)

    locked_columns = [c for c in payload["columns"]
                      if c not in config.LIVE_SNAPSHOT_COLUMNS]
    if locked_diffs:
        log.error(f"   DIFF {len(locked_diffs)} cell(s) in period-locked columns, "
                  f"e.g. {locked_diffs[:5]}")
        same = False
    else:
        log.info(f"   same: all {len(gen_rows)} rows x {len(locked_columns)} "
                 "period-locked columns identical to the reference")
    if live_diffs:
        moved = sorted({d.split('/')[2].split(':')[0] for d in live_diffs})
        log.warn(f"   live-snapshot movement in {moved}: {len(live_diffs)} cell(s) "
                 f"changed since the reference was built, e.g. {live_diffs[:3]}")
    else:
        log.info(f"   live-snapshot columns {list(config.LIVE_SNAPSHOT_COLUMNS)} "
                 "also unchanged")

    ref_kpi = {w: sum(k["returns"] for k in ref["kpi_windows"] if k["window_key"] == w)
               for w in config.KPI_WINDOWS}
    gen_kpi = {w: sum(k["returns"] for k in payload["kpi_windows"] if k["window_key"] == w)
               for w in config.KPI_WINDOWS}
    if ref_kpi != gen_kpi:
        log.error(f"   DIFF KPI windows: reference {ref_kpi} vs generated {gen_kpi}")
        same = False
    else:
        log.info(f"   same KPI windows: {gen_kpi}")

    if same:
        verdict = ("IDENTICAL" if not live_diffs else
                   f"IDENTICAL on every period-locked column "
                   f"({len(live_diffs)} live-snapshot cell(s) moved since)")
    else:
        verdict = f"DIFFERENT ({len(locked_diffs)} period-locked cell(s))"
    log.metric("comparison_result", verdict)
    return same


def main() -> int:
    ap = argparse.ArgumentParser(description="Return Analysis monthly automation")
    ap.add_argument("--dry-run", action="store_true",
                    help="run everything but do not publish or archive")
    ap.add_argument("--as-of", metavar="YYYY-MM-DD",
                    help="simulate the execution date (testing only)")
    ap.add_argument("--dates-only", action="store_true",
                    help="print the calculated periods and exit; no database access")
    ap.add_argument("--preflight", action="store_true",
                    help="environment readiness check only")
    ap.add_argument("--compare-with", metavar="DATASET.json",
                    help="dry run, then compare the result against a known dataset")
    args = ap.parse_args()

    if args.compare_with:
        args.dry_run = True

    execution_date = (dt.date.fromisoformat(args.as_of) if args.as_of else None)
    period = config.period_for(execution_date)

    run_id = dt.datetime.now(config.TIMEZONE).strftime("%Y%m%d_%H%M%S")
    log = logger_mod.RunLogger(run_id, period)
    log.info("")
    log.info("=" * 74)
    log.info(f"{config.PROJECT_NAME} ({config.PROJECT_CODE}) -- run {run_id}")

    try:
        # ---- 1. Scheduler / Trigger --------------------------------------
        log.stage(1, TOTAL_STEPS, "Scheduler / Trigger")
        log.metric("trigger", "scheduled task" if len(sys.argv) == 1 else "manual")
        log.metric("scheduled_as",
                   f"{config.TASK_NAME_SCHEDULER} -- {config.SCHEDULE_FREQUENCY} "
                   f"day {config.SCHEDULE_DAY_OF_MONTH} at {config.SCHEDULE_TIME} local")
        if args.as_of:
            log.warn(f"SIMULATED execution date {args.as_of} (--as-of)")

        # ---- 2. Configuration --------------------------------------------
        log.stage(2, TOTAL_STEPS, "Configuration (reporting dates calculated, never hardcoded)")
        log_period(log, period)
        log.metric("mode", "DRY RUN" if args.dry_run else "FULL")

        if args.dry_run:
            # A dry run must leave the project exactly as it found it, so its
            # evidence goes to the staging area instead of 05_Evidence/.
            config.AUTOMATION_VALIDATION_MD = (
                config.WORK_DIR / config.AUTOMATION_VALIDATION_MD.name)
            config.AUTOMATION_SOURCE_MD = (
                config.WORK_DIR / config.AUTOMATION_SOURCE_MD.name)
            log.info(f"   dry run: evidence is written to {config.WORK_DIR.name}/, "
                     "05_Evidence/ is not touched")

        if args.dates_only:
            log.info("dates only -- nothing else was touched")
            log.finish("DATES_ONLY")
            return 0

        problems = preflight(log, need_db=True)
        if problems:
            raise RuntimeError("; ".join(problems))
        if args.preflight:
            log.info("preflight only -- stopping here")
            log.finish("PREFLIGHT_OK")
            return 0

        # ---- 3. Fetch Data -------------------------------------------------
        log.stage(3, TOTAL_STEPS, "Fetch Data (live, read-only)")
        import fetch_data
        raw = fetch_data.fetch(period, log)

        # ---- 4. Validate Source Data ---------------------------------------
        log.stage(4, TOTAL_STEPS, "Validate Source Data")
        import validate_data
        validate_data.run(raw, period, log)

        # ---- 5. Process Business Logic -------------------------------------
        log.stage(5, TOTAL_STEPS, "Process Business Logic (approved formulas)")
        import process_data
        rows = process_data.run(raw, period, log)

        # ---- 6. Transform Data ----------------------------------------------
        log.stage(6, TOTAL_STEPS, "Transform Data")
        import transform_data
        payload = transform_data.run(rows, raw, period, log)

        # ---- 7. Generate Output ----------------------------------------------
        log.stage(7, TOTAL_STEPS, "Generate Output (standalone HTML)")
        import generate_dashboard
        generate_dashboard.run(payload, log)

        # ---- 8. Validate Output ------------------------------------------------
        log.stage(8, TOTAL_STEPS, "Validate Output (independent, vs live DB)")
        import validate_dashboard
        validation = validate_dashboard.run(payload, period, log)

        if args.compare_with:
            log.info("")
            log.info("-- comparison against a known dataset ------------------")
            identical = compare_with(args.compare_with, payload, log)
            if not identical:
                log.error("comparison FAILED - the generated report differs")

        # ---- 9. Publish / Store Output -------------------------------------------
        import archive
        import publish
        if args.dry_run:
            log.stage(9, TOTAL_STEPS, "Publish / Store Output")
            log.warn("DRY RUN -- the published report and the task board were NOT touched")
            log.metric("publish_result", "SKIPPED (dry run)")
            log.stage(10, TOTAL_STEPS, "Archive")
            log.warn("DRY RUN -- nothing archived")
            log.metric("archive_result", "SKIPPED (dry run)")
        else:
            log.stage(9, TOTAL_STEPS, "Publish / Store Output")
            archive.archive_live_output(log)          # never lose the outgoing month
            publish.run(log)
            log.stage(10, TOTAL_STEPS, "Archive")
            archive.archive_run(period, validation, log)
            publish.clean_work_dir(log)

        # ---- 11. Logging ------------------------------------------------------------
        log.stage(11, TOTAL_STEPS, "Logging")
        log.info(f"   execution date    : {period.execution_date}")
        log.info(f"   reporting month   : {period.month_key} ({period.month_label})")
        log.info(f"   last month period : {period.last_month_period}")
        log.info(f"   last year period  : {period.last_year_period}")
        log.info(f"   source rows       : {log.metrics.get('source_row_count')}")
        log.info(f"   generated rows    : {log.metrics.get('generated_row_count')}")
        log.info(f"   validation        : {validation['status']} "
                 f"({validation['checks_passed']}/{validation['checks_total']} checks, "
                 f"{validation['rows_validated']} rows)")
        log.info(f"   publish           : {log.metrics.get('publish_result')}")
        log.info(f"   archive           : {log.metrics.get('archive_result')}")
        log.clear_failure_notice()
        log.finish("SUCCESS")
        log.info("AUTOMATION COMPLETED")
        log.info("=" * 74)
        return 0

    except Exception as exc:                                # noqa: BLE001
        log.error(f"FAILED: {exc}")
        for line in traceback.format_exc().splitlines()[-12:]:
            log.error(f"   {line}")
        try:
            import archive
            archive.archive_failure(log)
        except Exception as inner:                          # noqa: BLE001
            log.error(f"   failure archiving also failed: {inner}")
        if config.LIVE_HTML.exists():
            log.error(f"   previous report RETAINED, unchanged: {config.LIVE_HTML}")
        log.notify_failure(str(exc))
        log.finish("FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())
