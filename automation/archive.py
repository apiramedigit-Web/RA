"""Step 10 -- Archive.

Every monthly report is kept under `07_Archive/<YYYY-MM>/`, named for the month
it reports on, so the full history stays available and nothing is lost when the
live deliverable is replaced.

Nothing is ever overwritten. If a folder for that month already exists (a
re-run of the same month), a numbered suffix is used instead.

Two moments archive:

* `archive_live_output()` runs BEFORE the live files are replaced. If the
  currently published report belongs to a month that has no archive folder yet
  -- which is the case for the first automated run, where August 2026 was built
  by hand -- it is preserved first.
* `archive_run()` runs AFTER a successful publish and stores the month that was
  just produced, together with its validation evidence.
"""
from __future__ import annotations

import datetime as dt
import json
import shutil
from pathlib import Path

import config


def _month_of_live_dataset() -> str | None:
    """The reporting month of whatever is currently published, from its own data."""
    if not config.LIVE_DATASET.exists():
        return None
    try:
        data = json.loads(config.LIVE_DATASET.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return None
    period = data.get("reporting_period", "")
    return period[:7] if len(period) >= 7 and period[4] == "-" else None


def _slot(month_key: str) -> Path:
    base = config.ARCHIVE_DIR / month_key
    if not base.exists():
        return base
    n = 2
    while (config.ARCHIVE_DIR / f"{month_key}_{n:02d}").exists():
        n += 1
    return config.ARCHIVE_DIR / f"{month_key}_{n:02d}"


def _copy_into(slot: Path, sources: list[tuple[Path, str]]) -> list[str]:
    slot.mkdir(parents=True, exist_ok=False)
    copied = []
    for src, name in sources:
        if src.exists():
            shutil.copy2(src, slot / name)
            copied.append(name)
    return copied


def archive_live_output(log) -> str | None:
    """Preserve the currently published report if its month is not archived yet."""
    month = _month_of_live_dataset()
    if not month:
        log.info("   nothing to preserve - no previously published report")
        return None
    if (config.ARCHIVE_DIR / month).exists():
        log.info(f"   {month} is already archived - left as it is, nothing overwritten")
        return None

    slot = _slot(month)
    copied = _copy_into(slot, [
        (config.LIVE_HTML, config.LIVE_HTML.name),
        (config.LIVE_DATASET, config.LIVE_DATASET.name),
    ])
    log.info(f"   preserved the existing {month} report -> "
             f"07_Archive/{slot.name} ({', '.join(copied)})")
    return slot.name


def archive_run(period: config.Period, validation: dict, log) -> str:
    """Archive the month that was just published, with its validation evidence."""
    slot = _slot(period.month_key)
    copied = _copy_into(slot, [
        (config.LIVE_HTML, config.LIVE_HTML.name),
        (config.LIVE_DATASET, config.LIVE_DATASET.name),
        (config.STAGING_VALIDATION, "validation_result.json"),
        (config.AUTOMATION_VALIDATION_MD, config.AUTOMATION_VALIDATION_MD.name),
        (config.AUTOMATION_SOURCE_MD, config.AUTOMATION_SOURCE_MD.name),
    ])

    (slot / "run_info.json").write_text(json.dumps({
        "reporting_month": period.month_key,
        "reporting_period": period.reporting_period,
        "last_month_period": period.last_month_period,
        "last_year_period": period.last_year_period,
        "execution_date": period.execution_date.isoformat(),
        "archived_at": dt.datetime.now(config.TIMEZONE).isoformat(timespec="seconds"),
        "validation": validation.get("status"),
        "rows": validation.get("rows_validated"),
    }, indent=2), encoding="utf-8")

    log.metric("archive_result", f"07_Archive/{slot.name}")
    log.info(f"   archived {len(copied) + 1} file(s): {', '.join(copied)}, run_info.json")
    _prune(log)
    return slot.name


def _prune(log) -> None:
    if config.ARCHIVE_RETENTION is None:
        return
    slots = sorted((p for p in config.ARCHIVE_DIR.iterdir() if p.is_dir()), reverse=True)
    for old in slots[config.ARCHIVE_RETENTION:]:
        shutil.rmtree(old, ignore_errors=True)
        log.info(f"   pruned old archive {old.name}")


def archive_failure(log) -> None:
    """Keep the staged artefacts of a failed run; the published report is untouched."""
    stamp = dt.datetime.now(config.TIMEZONE).strftime("%Y-%m-%d_%H%M%S")
    slot = config.ARCHIVE_DIR / f"FAILED_{stamp}"
    slot.mkdir(parents=True, exist_ok=True)
    for src in (config.STAGING_HTML, config.STAGING_DATASET, config.STAGING_VALIDATION):
        if src.exists():
            shutil.copy2(src, slot / src.name)
    log.info(f"   failure artefacts kept in 07_Archive/{slot.name} "
             "(published report untouched)")
