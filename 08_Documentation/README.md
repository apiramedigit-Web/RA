# 08_Documentation — handover and reference documents

Purpose: **documentation / handover** for the Return Analysis project.

This folder was added on 2026-09-18 because it was the only required purpose
with no location in the project. Every other purpose was already served by an
existing folder and those folders were reused unchanged.

## What belongs here

Handover notes, operating instructions for whoever picks the project up, and
reference material that is not evidence, not a requirement and not code.

## What does NOT belong here

This folder is **not** a second source of truth. Do not copy anything into it.

| Looking for | It lives in |
|---|---|
| Project documentation, how to rebuild and publish | `../README.md` (root) |
| Automation documentation, schedule, environment | `../automation/README.md` |
| The requirement itself | `../01_Requirements/` |
| Discovery, data mapping, gaps | `../05_Evidence/` (`01_`–`04_` series) |
| Validation results | `../05_Evidence/` |

The root `README.md` remains the project's primary documentation. If the two
ever disagree, the root `README.md` wins.
