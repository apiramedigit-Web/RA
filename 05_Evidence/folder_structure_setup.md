# Folder structure setup — evidence

- **Task:** Return Analysis
- **Project path:** `C:\Users\LED 222\eBay_Return_Analysis`
- **Date:** 2026-09-18
- **Governance:** Mini-AIOS Master Instruction & Skill Guide — Reuse → Extend → Merge → Create New
- **Status:** **PASS**

Scope was folder structure only. No dashboard logic, SQL, data, automation,
publisher logic, requirement or HTML was touched. Nothing was moved, renamed or
deleted.

---

## 1. Existing folders inspected

Full recursive inspection, including hidden and empty directories, before
anything was created.

| Folder | Files | Contents |
|---|---|---|
| `01_Requirements/` | 2 | `System Task - Return Analysis - kobiga.pdf` / `.csv` |
| `02_SQL/` | 2 | `ebay_return_analysis.sql`, `return_kpi_windows.sql` |
| `03_Build/` | 6 | `extract_dataset.py`, `build_dashboard.py`, `publish_ph_task.py`, `validate_dataset.py`, `validate_html.py`, `validate_filters.py` |
| `04_Data/` | 1 | `return_analysis_dataset.json` |
| `05_Evidence/` | 10 | discovery series `01_`–`04_`, validation and publish reports |
| `06_Output/` | 1 | `eBay_Return_Analysis.html` |
| `07_Archive/` | 0 (+1 subfolder) | `2026-08/` holding that month's HTML + dataset |
| `automation/` | 16 | 11 workflow modules, `run.py`, `scheduler.ps1`, tests, `README.md`, task XML |
| `automation/.work/` | 5 | staging area (transient, excluded from structure) |
| `logs/` | 3 | `execution.log`, `error.log`, `last_run_summary.json` |
| root | 1 | `README.md` |

---

## 2. Purpose coverage — existing folders reused

All nine required purposes were checked against **actual folder contents**, not
folder names.

| # | Required purpose | Served by | Decision |
|---|---|---|---|
| 1 | Requirement / source documents | `01_Requirements/` | **REUSE** |
| 2 | Discovery and data mapping | `05_Evidence/` — `01_requirement_extract.md`, `02_existing_asset_discovery.md`, `03_source_to_report_mapping.md`, `04_gaps_and_limits.md` | **REUSE** |
| 3 | Build / implementation | `02_SQL/` (queries), `03_Build/` (scripts), `automation/` (monthly pipeline) | **REUSE** |
| 4 | Final output | `06_Output/` | **REUSE** |
| 5 | Evidence | `05_Evidence/` | **REUSE** |
| 6 | Validation | scripts: `03_Build/validate_dataset.py`, `validate_html.py`, `validate_filters.py`, `automation/validate_data.py`, `automation/validate_dashboard.py` · reports: `05_Evidence/*validation*.md` | **REUSE** |
| 7 | Archive | `07_Archive/` (one folder per reporting month) | **REUSE** |
| 8 | Logs | `logs/` | **REUSE** |
| 9 | Documentation / handover | *no dedicated folder existed* | **CREATE** |

`04_Data/` holds the intermediate dataset artefact. It is not one of the nine
required purposes but is a legitimate existing folder — reused, untouched.

---

## 3. New folders created

| Folder | Reason |
|---|---|
| `08_Documentation/` | The only required purpose with no location. Follows the project's existing `NN_Name` convention rather than introducing a parallel scheme. Contains a short `README.md` that states its purpose and explicitly defers to the root `README.md` as the source of truth. |

**One folder created. One file created.** Nothing else.

---

## 4. Duplicate / conflicting folder structures found

**None created.** The preferred lowercase structure in the task brief
(`source/`, `discovery/`, `build/`, `output/`, `evidence/`, `validation/`,
`archive/`, `logs/`, `docs/`) was deliberately **not** applied, because the
project already carries equivalents under its `NN_Name` convention.

Duplicates that were explicitly avoided:

| Would-be new folder | Already served by | Action |
|---|---|---|
| `source/requirement/` | `01_Requirements/` | not created |
| `build/sql/` | `02_SQL/` | not created |
| `build/scripts/` | `03_Build/` | not created |
| `build/dashboard/` | `03_Build/build_dashboard.py` → `06_Output/` | not created |
| `output/` | `06_Output/` | not created |
| `evidence/` | `05_Evidence/` | not created |
| `archive/` | `07_Archive/` | not created |
| `logs/` | `logs/` (identical) | not created |
| `docs/` | created as `08_Documentation/` to match the existing convention | created once |

### Two purposes are served by shared folders — deliberate, not a gap

- **Discovery (2)** lives inside `05_Evidence/` as the numbered `01_`–`04_`
  series. Creating a separate `discovery/` would either sit empty while the real
  discovery documents stayed in `05_Evidence/`, or require moving files — which
  this task forbids. Splitting one purpose across two folders is worse than the
  current single clear location.
- **Validation (6)** is split by design between executable checks (`03_Build/`,
  `automation/`) and their reports (`05_Evidence/`). Creating an empty
  `06_Validation/` would add a third location for the same purpose. Not created.

Both are recorded here so the mapping is queryable without opening every folder.

---

## 5. Confirmation that no existing files were modified

Every file was checksummed before and after the change.

```
tracked before = 44 files      tracked after = 45 files

ADDED   (1):  ./08_Documentation/README.md
REMOVED (0):  none
CHANGED (0):  none
```

- **0 existing files modified**
- **0 files moved or renamed**
- **0 files deleted**
- **0 duplicate source-of-truth files created**
- ERA stream, unrelated users and unrelated projects: untouched

---

## 6. Final folder structure

```
eBay_Return_Analysis/
│
├── 01_Requirements/        # 1. Requirement / source documents
├── 02_SQL/                 # 3. Build — approved queries
├── 03_Build/               # 3. Build — scripts  · 6. Validation — scripts
├── 04_Data/                #    Intermediate dataset artefact
├── 05_Evidence/            # 5. Evidence · 2. Discovery & mapping · 6. Validation reports
├── 06_Output/              # 4. Final output — standalone HTML
├── 07_Archive/             # 7. Archive — one folder per reporting month
│   └── 2026-08/
├── 08_Documentation/       # 9. Documentation / handover          <- NEW
├── automation/             # 3. Build — monthly pipeline · 6. Validation — scripts
│   └── .work/              #    staging (transient)
├── logs/                   # 8. Logs
└── README.md               #    Project documentation (source of truth)
```

---

## 7. PASS criteria

| Criterion | Result |
|---|---|
| Clear location for source, discovery, build, output, evidence, validation, archive, logs, documentation | **PASS** — all nine mapped in section 2 |
| Existing equivalent folders reused | **PASS** — 8 of 9 purposes reused, 0 rebuilt |
| No unnecessary duplicate folder structure created | **PASS** — 9 duplicates avoided, listed in section 4 |
| No existing project files modified | **PASS** — checksum diff, 0 changed |
| Evidence of the structure setup saved | **PASS** — this file, in the existing `05_Evidence/` |

**Status: PASS**

Stopped after folder structure setup. No dashboard or automation change was made.
