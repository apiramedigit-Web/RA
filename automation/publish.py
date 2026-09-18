"""Step 9 -- Publish / Store Output.

Only ever called after Step 8 reported PASS.

Two things happen, in this order:

1. The validated staging files replace the live deliverables
   (`04_Data/return_analysis_dataset.json`, `06_Output/eBay_Return_Analysis.html`).
   The HTML is swapped atomically via `os.replace`, so a reader never sees a
   half-written file and a failure leaves the previous report intact.

2. The APPROVED publisher `03_Build/publish_ph_task.py` is imported and called
   as-is. Its scope is not touched by this automation: project_code `RA`, team
   `ebay_priors`, the same seven members, Thasanan still excluded, still an
   upsert on (project_code, assigned_user) inside one REPEATABLE READ
   transaction that verifies the stored md5 before committing. The separate
   `ERA` stream is never read or written.
"""
from __future__ import annotations

import importlib
import os
import shutil
import sys

import config


def promote(log) -> dict:
    """Move the validated staging files into the live deliverable paths."""
    for src in (config.STAGING_DATASET, config.STAGING_HTML):
        if not src.exists():
            raise RuntimeError(f"cannot publish - staging file missing: {src}")

    shutil.copy2(config.STAGING_DATASET, config.LIVE_DATASET)

    tmp = config.LIVE_HTML.with_suffix(".html.new")
    shutil.copy2(config.STAGING_HTML, tmp)
    os.replace(tmp, config.LIVE_HTML)             # atomic swap

    log.info(f"   published dataset -> {config.LIVE_DATASET}")
    log.info(f"   published report  -> {config.LIVE_HTML} "
             f"({config.LIVE_HTML.stat().st_size:,} bytes)")
    return {"html": str(config.LIVE_HTML), "dataset": str(config.LIVE_DATASET),
            "bytes": config.LIVE_HTML.stat().st_size}


def publish_task_board(log, dry_run: bool = False) -> str:
    """Run the approved ph_task publisher unchanged."""
    if not config.publish_db_available():
        raise RuntimeError(
            f"${config.PUBLISH_DB_ENV} is not set - the approved publisher writes "
            f"tech_team_outputs.ph_task in {config.PUBLISH_DB_NAME} through it")

    build_dir = str(config.BUILD_DIR)
    if build_dir not in sys.path:
        sys.path.insert(0, build_dir)
    if not config.PUBLISHER_MODULE.exists():
        raise RuntimeError(f"approved publisher missing: {config.PUBLISHER_MODULE}")

    publisher = importlib.reload(importlib.import_module("publish_ph_task"))

    log.info(f"   publisher: {config.PUBLISHER_MODULE.name} (approved, scope unchanged)")
    log.info(f"   target   : project_code={publisher.PROJECT_CODE} "
             f"team={publisher.TEAM} members={len(publisher.MEMBERS)} "
             f"excluded={','.join(publisher.EXCLUDED)}")

    argv = sys.argv
    sys.argv = ["publish_ph_task.py"] + (["--dry-run"] if dry_run else [])
    try:
        rc = publisher.main()
    finally:
        sys.argv = argv

    if rc != 0:
        raise RuntimeError(
            f"the approved publisher returned {rc} - the transaction was rolled "
            "back and nothing reached the task board")

    result = "DRY RUN (nothing written)" if dry_run else (
        f"{len(publisher.MEMBERS)} {publisher.PROJECT_CODE} cards updated")
    log.metric("publish_result", result)
    return result


def run(log, dry_run: bool = False) -> dict:
    published = promote(log)
    published["task_board"] = publish_task_board(log, dry_run=dry_run)
    return published


def clean_work_dir(log) -> None:
    for path in config.WORK_DIR.glob("*"):
        if path.is_file():
            path.unlink()
    log.info("   staging area cleared")
