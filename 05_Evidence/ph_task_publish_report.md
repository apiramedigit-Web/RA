# Return Analysis - ph_task publish report

- Published: 2026-09-17T12:15:47+00:00
- Table: `tech_team_outputs.ph_task` (database `order_management_copy`)
- project_code: `RA` · project_name: `Return Analysis` · team: `ebay_priors`
- developer: `Apirame` · version_level 1 · status `released`
- Source file: `C:\Users\LED 222\eBay_Return_Analysis\06_Output\eBay_Return_Analysis.html` (173,077 chars)
- html md5: `a2dcb22abbc517379f015d659e4a9e14` — verified identical on all 7 rows before commit
- Excluded by instruction: Thasanan

| Action | id | assigned_user | task_id |
|---|---|---|---|
| updated | 1713 | genga | `ra_genga_return_analysis_V001` |
| updated | 1714 | Jarsini | `ra_Jarsini_return_analysis_V001` |
| updated | 1715 | kobiga | `ra_kobiga_return_analysis_V001` |
| updated | 1716 | powsteena | `ra_powsteena_return_analysis_V001` |
| updated | 1717 | Sharmilan | `ra_Sharmilan_return_analysis_V001` |
| updated | 1718 | Sivajitha | `ra_Sivajitha_return_analysis_V001` |
| updated | 1719 | Thinesh | `ra_Thinesh_return_analysis_V001` |

## Verification performed inside the transaction

- row count for `RA` = 7 (expected 7)
- stored `md5(html_content)` matches the file on every row
- `team` and `version_status` correct on every row
- Thasanan absent from the result set
- row-count guard scoped to `project_code`, never the whole table
- REPEATABLE READ; any failure rolls the whole publish back
