"""Publish the Return Analysis dashboard to tech_team_outputs.ph_task.

Project code RA, team ebay_priors, one card per member (Thasanan excluded by
instruction). Upserts on (project_code, assigned_user) so re-running updates the
same seven rows instead of adding more.

Run with --dry-run to see exactly what would change without writing.
"""
import argparse
import datetime as dt
import hashlib
import json
import os
import pathlib
import sys
import time

import psycopg

BASE = pathlib.Path(__file__).resolve().parent.parent
HTML_FILE = BASE / "06_Output" / "eBay_Return_Analysis.html"
DATA_FILE = BASE / "04_Data" / "return_analysis_dataset.json"
EVIDENCE = BASE / "05_Evidence" / "ph_task_publish_report.md"

PROJECT_NAME = "Return Analysis"
PROJECT_CODE = "RA"
TASK_NAME = "Return Analysis Dashboard"
TEAM = "ebay_priors"
DEVELOPER = "Apirame"
VERSION_LEVEL = 1
PHASE_LEVEL = 1
VERSION_STATUS = "released"

# ebay_priors, excluding Thasanan by instruction. Casing matches the existing rows.
MEMBERS = ["genga", "Jarsini", "kobiga", "powsteena", "Sharmilan", "Sivajitha", "Thinesh"]
EXCLUDED = ["Thasanan"]


def connect(attempts=8, wait=15):
    """The server runs out of connection slots often; retry rather than fail the run."""
    dsn = os.environ["DATABASE_URL"]
    for i in range(1, attempts + 1):
        try:
            conn = psycopg.connect(dsn, connect_timeout=30)
            print(f"  connected on attempt {i}")
            return conn
        except psycopg.OperationalError as exc:
            if i == attempts:
                raise
            reason = "no free connection slots" if "slots" in str(exc) else str(exc).strip()[:50]
            print(f"  attempt {i}/{attempts}: {reason} - waiting {wait}s", flush=True)
            time.sleep(wait)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--attempts", type=int, default=8)
    parser.add_argument("--wait", type=int, default=15)
    args = parser.parse_args()

    # read_text() normalises newlines, so the md5 matches what Postgres stores.
    html = HTML_FILE.read_text(encoding="utf-8")
    html_md5 = hashlib.md5(html.encode("utf-8")).hexdigest()
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))

    kpi = {w: sum(k["returns"] for k in data["kpi_windows"] if k["window_key"] == w)
           for w in ("period", "last_month", "last_year")}
    accounts = len({r["Account"] for r in data["rows"]})
    markets = len({r["Market Place"] for r in data["rows"]})

    description = (
        f'eBay Return Analysis for {data["reporting_period"]}. '
        f'{data["row_count"]} Listing/SKU rows covering {kpi["period"]} returns across '
        f"{accounts} accounts and {markets} marketplaces. All 23 required columns "
        "(Listing ID, SKU, Product Title, Account, Market Place, Total Orders, Returns, "
        "Return Rate, Last Month Returns and %, Last Year Returns and %, Refund, "
        "Return Cost, Main Return Reason, Return Rank, Negative Feedback, Open Cases, "
        "Stock, Ad Spend, Ad Sales, ACOS, ROAS). Filter by Account, Market Place, SKU "
        f'and Listing ID. KPI cards: {kpi["period"]} returns this month, '
        f'{kpi["last_month"]} last month, {kpi["last_year"]} the same month last year. '
        f'Source database ledsone, snapshot {data["snapshot_utc"]}. '
        "Standalone HTML - no server or database needed to open it."
    )

    print(f"HTML  : {HTML_FILE.name}  {len(html):,} chars  md5 {html_md5}")
    print(f"Target: {PROJECT_CODE} / {TEAM} / {len(MEMBERS)} members "
          f"(excluded: {', '.join(EXCLUDED)})")

    conn = connect(args.attempts, args.wait)
    try:
        conn.autocommit = False
        with conn.cursor() as cur:
            cur.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")

            # Guard: only ever counts rows for THIS project code, never the whole table.
            cur.execute("SELECT count(*) FROM tech_team_outputs.ph_task WHERE project_code=%s",
                        (PROJECT_CODE,))
            before = cur.fetchone()[0]
            cur.execute(
                "SELECT assigned_user, id FROM tech_team_outputs.ph_task "
                "WHERE project_code=%s ORDER BY assigned_user", (PROJECT_CODE,))
            existing = dict(cur.fetchall())
            print(f"Before: {before} rows for project_code={PROJECT_CODE} "
                  f"{('(' + ', '.join(existing) + ')') if existing else '(new project code)'}")

            if args.dry_run:
                for m in MEMBERS:
                    verb = "UPDATE id " + str(existing[m]) if m in existing else "INSERT new row"
                    print(f"  would {verb:<18} for {m}")
                conn.rollback()
                print("\nDry run - nothing written.")
                return 0

            touched = []
            for member in MEMBERS:
                task_id = f"ra_{member}_return_analysis_V{VERSION_LEVEL:03d}"
                if member in existing:
                    cur.execute(
                        """UPDATE tech_team_outputs.ph_task
                           SET project_name=%s, task_name=%s, task_id=%s, team=%s,
                               developer=%s, html_content=%s, description=%s,
                               phase_level=%s, version_level=%s, version_status=%s,
                               updated_at=now()
                         WHERE id=%s RETURNING id""",
                        (PROJECT_NAME, TASK_NAME, task_id, TEAM, DEVELOPER, html,
                         description, PHASE_LEVEL, VERSION_LEVEL, VERSION_STATUS,
                         existing[member]))
                    touched.append(("updated", member, cur.fetchone()[0]))
                else:
                    cur.execute(
                        """INSERT INTO tech_team_outputs.ph_task
                           (project_name, project_code, task_name, task_id, team, developer,
                            assigned_user, html_content, description, phase_level,
                            version_level, version_status)
                           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                        (PROJECT_NAME, PROJECT_CODE, TASK_NAME, task_id, TEAM, DEVELOPER,
                         member, html, description, PHASE_LEVEL, VERSION_LEVEL,
                         VERSION_STATUS))
                    touched.append(("inserted", member, cur.fetchone()[0]))

            # Verify inside the transaction, before committing.
            cur.execute(
                """SELECT assigned_user, id, md5(html_content), length(html_content),
                          task_id, team, version_status
                     FROM tech_team_outputs.ph_task
                    WHERE project_code=%s ORDER BY id""", (PROJECT_CODE,))
            rows = cur.fetchall()
            cur.execute("SELECT count(*) FROM tech_team_outputs.ph_task WHERE project_code=%s",
                        (PROJECT_CODE,))
            after = cur.fetchone()[0]

            problems = []
            if after != len(MEMBERS):
                problems.append(f"expected {len(MEMBERS)} rows for {PROJECT_CODE}, found {after}")
            if {r[0] for r in rows} != set(MEMBERS):
                problems.append(f"member set mismatch: {sorted({r[0] for r in rows})}")
            for user, _id, md5, _len, _tid, team, status in rows:
                if md5 != html_md5:
                    problems.append(f"{user}: stored md5 {md5} != file md5 {html_md5}")
                if team != TEAM or status != VERSION_STATUS:
                    problems.append(f"{user}: team/status wrong ({team}/{status})")
            for excluded in EXCLUDED:
                if excluded in {r[0] for r in rows}:
                    problems.append(f"{excluded} must not receive this task")

            if problems:
                conn.rollback()
                print("\nROLLED BACK - verification failed:")
                for p in problems:
                    print("  -", p)
                return 1

            conn.commit()
    finally:
        conn.close()

    print(f"\nAfter : {after} rows for project_code={PROJECT_CODE}")
    for action, member, row_id in touched:
        print(f"  {action:8} id={row_id:<5} {member}")

    lines = [
        "# Return Analysis - ph_task publish report", "",
        f"- Published: {dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')}",
        f"- Table: `tech_team_outputs.ph_task` (database `order_management_copy`)",
        f"- project_code: `{PROJECT_CODE}` · project_name: `{PROJECT_NAME}` · team: `{TEAM}`",
        f"- developer: `{DEVELOPER}` · version_level {VERSION_LEVEL} · status `{VERSION_STATUS}`",
        f"- Source file: `{HTML_FILE}` ({len(html):,} chars)",
        f"- html md5: `{html_md5}` — verified identical on all {after} rows before commit",
        f"- Excluded by instruction: {', '.join(EXCLUDED)}", "",
        "| Action | id | assigned_user | task_id |", "|---|---|---|---|",
    ]
    lines += [f"| {a} | {i} | {m} | `ra_{m}_return_analysis_V{VERSION_LEVEL:03d}` |"
              for a, m, i in touched]
    lines += ["", "## Verification performed inside the transaction", "",
              f"- row count for `{PROJECT_CODE}` = {after} (expected {len(MEMBERS)})",
              "- stored `md5(html_content)` matches the file on every row",
              "- `team` and `version_status` correct on every row",
              f"- {', '.join(EXCLUDED)} absent from the result set",
              "- row-count guard scoped to `project_code`, never the whole table",
              "- REPEATABLE READ; any failure rolls the whole publish back"]
    EVIDENCE.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"\nEvidence -> {EVIDENCE}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
