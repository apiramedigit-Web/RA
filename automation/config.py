"""Configuration for the eBay Return Analysis (RA) monthly automation.

Step 2 of the Common Automation Workflow.

Nothing is hardcoded in the workflow modules: every path, credential source,
reporting date and business constant is resolved here.

REPORTING DATES ARE NEVER HARDCODED. They are derived from the execution date:

    reporting month = the calendar month BEFORE the month the run starts in

        run 2026-09-01  ->  reporting period 2026-08   (last month 2026-07, last year 2025-08)
        run 2026-10-01  ->  reporting period 2026-09   (last month 2026-08, last year 2025-09)
        run 2026-11-01  ->  reporting period 2026-10   (last month 2026-09, last year 2025-10)

All windows are half-open calendar months: start <= request_date < end.

BUSINESS LOGIC LIVES ELSEWHERE AND IS NOT RESTATED HERE. The approved
Return Analysis logic stays in `02_SQL/*.sql` and `03_Build/build_dashboard.py`;
this automation drives those approved artefacts, it does not reimplement them.
"""
from __future__ import annotations

import datetime as dt
import os
from pathlib import Path
from zoneinfo import ZoneInfo

# --------------------------------------------------------------------------
# Project identity -- matches the approved publisher metadata exactly
# --------------------------------------------------------------------------
PROJECT_NAME = "Return Analysis"
PROJECT_CODE = "RA"
REPORT_TITLE = "eBay Return Analysis"
REQUIREMENT = "System Task - Return Analysis - kobiga.pdf"
DEVELOPER = "Apirame"

# --------------------------------------------------------------------------
# Schedule -- 1st day of every month, local machine time.
# Windows Task Scheduler fires on local time and has no per-task timezone.
# TIMEZONE below only stamps run ids, log lines and the execution date.
# --------------------------------------------------------------------------
SCHEDULE_FREQUENCY = "MONTHLY"
SCHEDULE_DAY_OF_MONTH = 1
SCHEDULE_TIME = "07:00"
TASK_NAME_SCHEDULER = "RA_Monthly_Return_Analysis"
try:
    TIMEZONE = dt.datetime.now().astimezone().tzinfo
except Exception:                                       # pragma: no cover
    TIMEZONE = ZoneInfo("UTC")


# --------------------------------------------------------------------------
# Dynamic reporting period (Step 2)
# --------------------------------------------------------------------------
def _first_of_month(d: dt.date) -> dt.date:
    return d.replace(day=1)


def _add_months(first: dt.date, months: int) -> dt.date:
    """Move a first-of-month date by whole months. Always lands on day 1."""
    total = (first.year * 12 + first.month - 1) + months
    return dt.date(total // 12, total % 12 + 1, 1)


class Period:
    """The six calendar-month boundaries this run reports on.

    Half-open throughout:  start <= request_date < end.
    """

    __slots__ = ("execution_date", "current_start", "current_end",
                 "last_month_start", "last_month_end",
                 "last_year_start", "last_year_end")

    def __init__(self, execution_date: dt.date) -> None:
        self.execution_date = execution_date
        run_month = _first_of_month(execution_date)

        # Reporting period = the previous calendar month.
        self.current_start = _add_months(run_month, -1)
        self.current_end = run_month

        # Last Month = the calendar month immediately before the reporting period.
        self.last_month_start = _add_months(self.current_start, -1)
        self.last_month_end = self.current_start

        # Last Year = the same calendar month one year earlier.
        self.last_year_start = _add_months(self.current_start, -12)
        self.last_year_end = _add_months(self.current_end, -12)

    # ---- identity ---------------------------------------------------------
    @property
    def month_key(self) -> str:
        """YYYY-MM of the reporting month -- the archive folder name."""
        return self.current_start.strftime("%Y-%m")

    @property
    def month_label(self) -> str:
        """e.g. 'August 2026' -- for logs and the publish description."""
        return self.current_start.strftime("%B %Y")

    @property
    def last_month_label(self) -> str:
        return self.last_month_start.strftime("%B %Y")

    @property
    def last_year_label(self) -> str:
        return self.last_year_start.strftime("%B %Y")

    # ---- the inclusive "start to end" strings the dashboard header shows ---
    @staticmethod
    def _span(start: dt.date, end: dt.date) -> str:
        return f"{start.isoformat()} to {(end - dt.timedelta(days=1)).isoformat()}"

    @property
    def reporting_period(self) -> str:
        return self._span(self.current_start, self.current_end)

    @property
    def last_month_period(self) -> str:
        return self._span(self.last_month_start, self.last_month_end)

    @property
    def last_year_period(self) -> str:
        return self._span(self.last_year_start, self.last_year_end)

    # ---- the six literals the approved SQL's `params` CTE needs ----------
    def sql_literals(self) -> dict[str, str]:
        return {
            "p_start": self.current_start.isoformat(),
            "p_end": self.current_end.isoformat(),
            "lm_start": self.last_month_start.isoformat(),
            "lm_end": self.last_month_end.isoformat(),
            "ly_start": self.last_year_start.isoformat(),
            "ly_end": self.last_year_end.isoformat(),
        }

    def as_dict(self) -> dict[str, str]:
        d = {"execution_date": self.execution_date.isoformat(),
             "reporting_month": self.month_key}
        d.update(self.sql_literals())
        return d

    def __repr__(self) -> str:                           # pragma: no cover
        return (f"Period(run={self.execution_date}, reporting={self.month_key}, "
                f"lm={self.last_month_start:%Y-%m}, ly={self.last_year_start:%Y-%m})")


def period_for(execution_date: dt.date | None = None) -> Period:
    """The reporting period for a run starting on `execution_date` (default: today)."""
    return Period(execution_date or dt.datetime.now(TIMEZONE).date())


# --------------------------------------------------------------------------
# Paths -- the automation drives the existing approved project layout
# --------------------------------------------------------------------------
AUTOMATION_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = AUTOMATION_DIR.parent

SQL_DIR = PROJECT_ROOT / "02_SQL"
BUILD_DIR = PROJECT_ROOT / "03_Build"
DATA_DIR = PROJECT_ROOT / "04_Data"
EVIDENCE_DIR = PROJECT_ROOT / "05_Evidence"
OUTPUT_DIR = PROJECT_ROOT / "06_Output"
ARCHIVE_DIR = PROJECT_ROOT / "07_Archive"
LOG_DIR = PROJECT_ROOT / "logs"
WORK_DIR = AUTOMATION_DIR / ".work"          # staging -- never published from

# Approved artefacts the automation reuses. Business logic is read from these.
SQL_DATASET = SQL_DIR / "ebay_return_analysis.sql"
SQL_KPI_WINDOWS = SQL_DIR / "return_kpi_windows.sql"
BUILDER_MODULE = BUILD_DIR / "build_dashboard.py"
PUBLISHER_MODULE = BUILD_DIR / "publish_ph_task.py"

# Live deliverables (the names the approved project already publishes under).
LIVE_DATASET = DATA_DIR / "return_analysis_dataset.json"
LIVE_HTML = OUTPUT_DIR / "eBay_Return_Analysis.html"

# Staging copies -- everything is built and validated here first.
STAGING_DATASET = WORK_DIR / "staging_return_analysis_dataset.json"
STAGING_HTML = WORK_DIR / "staging_eBay_Return_Analysis.html"
STAGING_VALIDATION = WORK_DIR / "staging_validation_result.json"

# Evidence written by the automation (alongside the existing manual evidence).
AUTOMATION_VALIDATION_MD = EVIDENCE_DIR / "automation_validation_report.md"
AUTOMATION_SOURCE_MD = EVIDENCE_DIR / "automation_source_validation_report.md"

for _d in (DATA_DIR, EVIDENCE_DIR, OUTPUT_DIR, ARCHIVE_DIR, LOG_DIR, WORK_DIR):
    _d.mkdir(parents=True, exist_ok=True)

EXECUTION_LOG = LOG_DIR / "execution.log"
ERROR_LOG = LOG_DIR / "error.log"
RUN_SUMMARY_JSON = LOG_DIR / "last_run_summary.json"
FAILURE_NOTICE = LOG_DIR / "FAILURE_NOTICE.txt"

# --------------------------------------------------------------------------
# Databases -- read from the environment only, never written to a file or log
# --------------------------------------------------------------------------
# Source (read-only): the `ledsone` warehouse the approved SQL runs against.
# ERA_SOURCE_DB_URL keeps the override name the existing 03_Build scripts accept.
SOURCE_DB_ENVS = ("ERA_SOURCE_DB_URL", "WLP_SOURCE_DB_URL")
SOURCE_DB_NAME = "ledsone"

# Publish target: tech_team_outputs.ph_task in order_management_copy.
PUBLISH_DB_ENV = "DATABASE_URL"
PUBLISH_DB_NAME = "order_management_copy"

DB_CONNECT_TIMEOUT = 60
DB_STATEMENT_TIMEOUT_MS = 900_000               # 15 minutes


def source_db_url() -> str:
    for name in SOURCE_DB_ENVS:
        url = os.environ.get(name)
        if url:
            return url
    raise RuntimeError(
        f"None of {' / '.join(SOURCE_DB_ENVS)} is set. The automation reads "
        f"{SOURCE_DB_NAME} through it and will not run without it. Set it as a "
        "USER-level environment variable so the scheduled task inherits it:  "
        f"[Environment]::SetEnvironmentVariable('{SOURCE_DB_ENVS[1]}','<dsn>','User')")


def source_db_available() -> bool:
    return any(os.environ.get(n) for n in SOURCE_DB_ENVS)


def publish_db_available() -> bool:
    return bool(os.environ.get(PUBLISH_DB_ENV))


# --------------------------------------------------------------------------
# Report contract -- the approved column list, in the approved order.
# Identical to 03_Build/extract_dataset.py. Changing this is a requirement
# change, not an automation change.
# --------------------------------------------------------------------------
COLUMNS = (
    "Listing ID", "SKU", "Product Title", "Account", "Market Place",
    "Total Orders", "Returns", "Return Rate",
    "Last Month Returns", "Last Month Returns %",
    "Last Year Returns", "Last Year Returns %",
    "Refund (£)", "Last Month Refund (£)", "Return Cost (£)", "Main Return Reason",
    "Return Rank", "Negative Feedback", "Open Cases", "Stock",
    "Ad Spend (£)", "Ad Sales (£)", "ACOS", "ROAS",
)
# The SQL aliases carry no currency symbol; map them onto the required names.
ALIAS_TO_COLUMN = {c.replace(" (£)", ""): c for c in COLUMNS}

KPI_WINDOWS = ("period", "last_month", "last_year")

# Two approved columns are read as at the moment of the run, not as at the end
# of the reporting month, so re-running a month legitimately moves them:
#   Stock       - `local_inventory_current_stock_location_wise` holds CURRENT
#                 stock only and cannot be restated for a past month
#                 (05_Evidence/04_gaps_and_limits.md, G5)
#   Open Cases  - `current_state <> 'CLOSED'` is the return's status right now,
#                 so a return that closes after the report is built stops
#                 counting as open
# Used only by the dry-run comparison, to tell genuine source movement apart
# from a real difference. Nothing about how they are calculated changes.
LIVE_SNAPSHOT_COLUMNS = ("Stock", "Open Cases")

# Raw return reasons the source is known to emit. A value outside this set is
# reported as a warning (new source value), never silently rewritten.
KNOWN_RETURN_REASONS = frozenset({
    "ORDERED_WRONG_ITEM", "WRONG_SIZE", "NOT_AS_DESCRIBED", "ORDERED_ACCIDENTALLY",
    "DEFECTIVE_ITEM", "ARRIVED_DAMAGED", "NO_LONGER_NEED_ITEM",
    "ORDERED_DIFFERENT_ITEM", "MISSING_PARTS",
})

# --------------------------------------------------------------------------
# Source-data validation thresholds (Step 4).
# Deliberately wide: they catch a broken pipeline, not normal monthly drift.
# --------------------------------------------------------------------------
REQUIRED_SOURCE_TABLES = (
    "customer_service.ebay_returns",
    "order_management.order_item_info",
    "order_management.orders",
    "order_management.sub_source",
    "order_management.source",
    "ebay_campaigns.performance_data",
    "accounting.ebay_order_expenses",
    "customer_service.ebay_orders_customer_feedbacks",
    "inventory.products",
    "inventory.local_inventory_current_stock_location_wise",
)
MIN_PERIOD_RETURNS = 10          # a month below this is almost certainly a load failure
MIN_REPORT_ROWS = 5
MAX_MISSING_ACCOUNT_PCT = 5.0    # % of period returns with no sub_source mapping

# --------------------------------------------------------------------------
# Output validation (Step 8)
# --------------------------------------------------------------------------
MONEY_TOLERANCE = 0.02           # £ rounding tolerance on aggregate reconciliations
RATE_TOLERANCE = 0.011           # percentage-point tolerance on recomputed rates
AD_TOLERANCE = 0.06              # ads are allocated pro-rata, so slightly wider
MIN_HTML_BYTES = 100_000
# A credential, a template token or a rendered-bad-value must never appear.
FORBIDDEN_HTML_MARKERS = (
    "postgresql://", "postgres://", "DATABASE_URL", "WLP_SOURCE_DB_URL",
    "password=", ">undefined<", ">NaN<", ">None<",
)

# --------------------------------------------------------------------------
# Archive (Step 10) -- 07_Archive/<YYYY-MM>/ , never overwritten
# --------------------------------------------------------------------------
ARCHIVE_RETENTION = None                 # None = keep every historical month

# --------------------------------------------------------------------------
# Failure handling
# --------------------------------------------------------------------------
NOTIFY_ON_FAILURE = True
