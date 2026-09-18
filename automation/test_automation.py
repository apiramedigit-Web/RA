"""Tests for the Return Analysis (RA) monthly automation.

No database access. These prove the date arithmetic and that no reporting
month is hardcoded anywhere in the automation.

    python test_automation.py
"""
from __future__ import annotations

import datetime as dt
import re
import sys

import config

FAILURES: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"{'PASS' if ok else 'FAIL'}  {name}{(' - ' + detail) if detail else ''}")
    if not ok:
        FAILURES.append(f"{name} ({detail})")


def eq(name: str, got, want) -> None:
    check(name, got == want, f"got {got!r}, want {want!r}")


# ---------------------------------------------------------------------------
# 1. The three scenarios the requirement names
# ---------------------------------------------------------------------------
print("\n-- required scenarios --------------------------------------------")
SCENARIOS = [
    # run date,      reporting,  last month, last year
    ("2026-09-01", "2026-08", "2026-07", "2025-08"),
    ("2026-10-01", "2026-09", "2026-08", "2025-09"),
    ("2026-11-01", "2026-10", "2026-09", "2025-10"),
]
for run_date, reporting, last_month, last_year in SCENARIOS:
    p = config.period_for(dt.date.fromisoformat(run_date))
    eq(f"run {run_date} -> reporting month", p.month_key, reporting)
    eq(f"run {run_date} -> last month", p.last_month_start.strftime("%Y-%m"), last_month)
    eq(f"run {run_date} -> last year", p.last_year_start.strftime("%Y-%m"), last_year)

# ---------------------------------------------------------------------------
# 2. Half-open calendar-month boundaries
# ---------------------------------------------------------------------------
print("\n-- half-open calendar boundaries ---------------------------------")
p = config.period_for(dt.date(2026, 9, 1))
eq("current_start", p.current_start, dt.date(2026, 8, 1))
eq("current_end", p.current_end, dt.date(2026, 9, 1))
eq("last_month_start", p.last_month_start, dt.date(2026, 7, 1))
eq("last_month_end == current_start", p.last_month_end, p.current_start)
eq("last_year_start", p.last_year_start, dt.date(2025, 8, 1))
eq("last_year_end", p.last_year_end, dt.date(2025, 9, 1))
check("every boundary is the 1st of a month",
      all(d.day == 1 for d in (p.current_start, p.current_end, p.last_month_start,
                               p.last_month_end, p.last_year_start, p.last_year_end)))
eq("SQL literals", p.sql_literals(), {
    "p_start": "2026-08-01", "p_end": "2026-09-01",
    "lm_start": "2026-07-01", "lm_end": "2026-08-01",
    "ly_start": "2025-08-01", "ly_end": "2025-09-01"})
eq("reporting_period label", p.reporting_period, "2026-08-01 to 2026-08-31")
eq("last_month_period label", p.last_month_period, "2026-07-01 to 2026-07-31")
eq("last_year_period label", p.last_year_period, "2025-08-01 to 2025-08-31")

# ---------------------------------------------------------------------------
# 3. Year and month-length edge cases
# ---------------------------------------------------------------------------
print("\n-- edge cases ----------------------------------------------------")
jan = config.period_for(dt.date(2027, 1, 1))
eq("January run rolls the year back", jan.month_key, "2026-12")
eq("January run last month", jan.last_month_start, dt.date(2026, 11, 1))
eq("January run last year", jan.last_year_start, dt.date(2025, 12, 1))

mar = config.period_for(dt.date(2028, 3, 1))
eq("March 2028 reports February (leap year)", mar.month_key, "2028-02")
eq("February 2028 spans 29 days", mar.reporting_period, "2028-02-01 to 2028-02-29")
eq("last year February 2027 spans 28 days", mar.last_year_period,
   "2027-02-01 to 2027-02-28")

mid = config.period_for(dt.date(2026, 9, 18))
eq("a mid-month run still reports the previous month", mid.month_key, "2026-08")
eq("a mid-month run matches the 1st-of-month run",
   mid.sql_literals(), config.period_for(dt.date(2026, 9, 1)).sql_literals())

# Every month of a four-year span must produce a consistent set of windows.
bad = []
for year in range(2025, 2029):
    for month in range(1, 13):
        q = config.period_for(dt.date(year, month, 1))
        if not (q.last_month_end == q.current_start
                and q.current_end == dt.date(year, month, 1)
                and q.last_year_start == dt.date(q.current_start.year - 1,
                                                 q.current_start.month, 1)
                and q.last_year_end == dt.date(q.current_end.year - 1,
                                               q.current_end.month, 1)):
            bad.append(f"{year}-{month:02d}")
check("48 consecutive monthly runs all produce consistent windows",
      not bad, f"broken: {bad}")

# ---------------------------------------------------------------------------
# 4. No hardcoded reporting month anywhere in the automation
# ---------------------------------------------------------------------------
print("\n-- no hardcoded dates in the automation --------------------------")
DATE_LITERAL = re.compile(r"\b(19|20)\d{2}-\d{2}(-\d{2})?\b")
MONTH_LITERAL = re.compile(
    r"\b(January|February|March|April|May|June|July|August|September|October|"
    r"November|December)\s+(19|20)\d{2}\b")

PRODUCTION_PY = sorted(p for p in config.AUTOMATION_DIR.glob("*.py")
                       if p.name != "test_automation.py")
PRODUCTION_PS1 = sorted(config.AUTOMATION_DIR.glob("*.ps1"))


def code_strings(path):
    """Every string literal in the file's EXECUTABLE code.

    Comments never reach the AST, and docstrings are dropped, so prose that
    explains the date arithmetic cannot mask a real hardcoded value.
    """
    import ast
    tree = ast.parse(path.read_text(encoding="utf-8"))
    docstrings = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef,
                             ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
            if body and isinstance(body[0], ast.Expr) \
                    and isinstance(body[0].value, ast.Constant) \
                    and isinstance(body[0].value.value, str):
                docstrings.add(id(body[0].value))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) \
                and id(node) not in docstrings:
            yield getattr(node, "lineno", 0), node.value


def ps1_code_lines(path):
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        yield n, line.split("#", 1)[0]


offenders = []
for path in PRODUCTION_PY:
    for lineno, value in code_strings(path):
        if "%Y-%m" in value or "%Y" in value or "%B" in value:
            continue                                   # a format string, not a date
        if DATE_LITERAL.search(value) or MONTH_LITERAL.search(value):
            offenders.append(f"{path.name}:{lineno}: {value[:80]!r}")
for path in PRODUCTION_PS1:
    for lineno, line in ps1_code_lines(path):
        if "yyyy-MM" in line or "%Y-%m" in line:
            continue
        if DATE_LITERAL.search(line) or MONTH_LITERAL.search(line):
            offenders.append(f"{path.name}:{lineno}: {line.strip()[:80]}")

check("no production automation file contains a hardcoded calendar date in code",
      not offenders, "; ".join(offenders[:5]))

# The three months of the existing manual build must not appear as values.
banned = ("2026-08", "2026-07", "2025-08", "August 2026", "July 2026", "August 2025")
hits = []
for path in PRODUCTION_PY:
    for lineno, value in code_strings(path):
        for token in banned:
            if token in value:
                hits.append(f"{path.name}:{lineno} contains {token!r}")
for path in PRODUCTION_PS1:
    for lineno, line in ps1_code_lines(path):
        for token in banned:
            if token in line:
                hits.append(f"{path.name}:{lineno} contains {token!r}")
check("no August 2026 / July 2026 / August 2025 hardcoding remains in code",
      not hits, "; ".join(hits[:5]))

# ---------------------------------------------------------------------------
# 5. The approved SQL is reused, with only its six date literals substituted
# ---------------------------------------------------------------------------
print("\n-- approved SQL is reused, dates substituted only ----------------")
import fetch_data

for sql_file in (config.SQL_DATASET, config.SQL_KPI_WINDOWS):
    original = sql_file.read_text(encoding="utf-8")
    rendered = fetch_data.render_sql(sql_file, p)

    # Only the six literals may differ.
    diff_lines = [(a, b) for a, b in zip(original.splitlines(), rendered.splitlines())
                  if a != b]
    check(f"{sql_file.name}: only the params CTE lines change",
          len(diff_lines) <= 3, f"{len(diff_lines)} changed line(s)")
    check(f"{sql_file.name}: same number of lines",
          len(original.splitlines()) == len(rendered.splitlines()))
    check(f"{sql_file.name}: this run's dates are present",
          all(f"DATE '{v}'" in rendered for v in p.sql_literals().values()))

    # Rendering with a different month must actually move every window.
    other = config.period_for(dt.date(2026, 11, 1))
    rendered_other = fetch_data.render_sql(sql_file, other)
    check(f"{sql_file.name}: a different run date produces different SQL",
          rendered_other != rendered)
    check(f"{sql_file.name}: rendering is deterministic",
          fetch_data.render_sql(sql_file, p) == rendered)

# ---------------------------------------------------------------------------
# 6. The report contract is the approved one
# ---------------------------------------------------------------------------
print("\n-- report contract -----------------------------------------------")
eq("column count", len(config.COLUMNS), 24)
check("column order matches the approved dataset",
      list(config.COLUMNS)[:5] == ["Listing ID", "SKU", "Product Title",
                                   "Account", "Market Place"])
check("every SQL alias maps to exactly one column",
      len(config.ALIAS_TO_COLUMN) == len(config.COLUMNS))

print()
if FAILURES:
    print(f"{len(FAILURES)} FAILURE(S):")
    for f in FAILURES:
        print("  -", f)
    sys.exit(1)
print("all tests passed")
