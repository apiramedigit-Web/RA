"""Step 7 -- Generate Output.

Renders the standalone HTML Return Analysis dashboard.

The renderer is NOT reimplemented here. `03_Build/build_dashboard.py` is the
approved builder and it is imported and called as-is, with its two file paths
pointed at the staging area for the duration of the call. Layout, columns,
formatting, filters and KPI cards therefore come out byte-for-byte the way the
approved build produces them -- the only thing that differs between months is
the data and the three period labels inside the dataset.
"""
from __future__ import annotations

import importlib
import sys

import config


def _load_builder():
    build_dir = str(config.BUILD_DIR)
    if build_dir not in sys.path:
        sys.path.insert(0, build_dir)
    if not config.BUILDER_MODULE.exists():
        raise RuntimeError(f"approved builder missing: {config.BUILDER_MODULE}")
    module = importlib.import_module("build_dashboard")
    return importlib.reload(module)


def run(payload: dict, log) -> dict:
    builder = _load_builder()

    original_data, original_out = builder.DATA_FILE, builder.OUT_FILE
    try:
        builder.DATA_FILE = config.STAGING_DATASET
        builder.OUT_FILE = config.STAGING_HTML
        builder.main()
    finally:
        builder.DATA_FILE, builder.OUT_FILE = original_data, original_out

    if not config.STAGING_HTML.exists():
        raise RuntimeError("the builder produced no HTML")

    size = config.STAGING_HTML.stat().st_size
    if size < config.MIN_HTML_BYTES:
        raise RuntimeError(
            f"generated HTML is only {size:,} bytes, minimum {config.MIN_HTML_BYTES:,}")

    log.metric("generated_html_bytes", size)
    log.info(f"   renderer: {config.BUILDER_MODULE.name} (approved, unmodified)")
    log.info(f"   staged HTML -> {config.STAGING_HTML.name}")

    return {"html": config.STAGING_HTML, "bytes": size,
            "rows": payload["row_count"]}
