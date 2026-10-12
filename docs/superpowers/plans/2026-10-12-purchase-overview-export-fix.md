# Purchase Overview Export Fix

> **For agentic workers:** Execute inline with executing-plans; preserve the production deployment boundary.

**Goal:** Fix the confirmed SQL Server 169 error when exporting purchase overview sorted by project code.

**Architecture:** Share a stable, deduplicated ordering expression between overview pagination and streaming export. Keep query predicates, organization authorization, accounting and export permissions unchanged.

**Tech Stack:** Python, FastAPI, SQL Server, unittest with the existing relational SQLite ERP fixture.

## Constraints

- User approved the export repair on 2026-10-12. No schema upgrade, production writes, release, merge or push.
- User clarified that conversion counts only fully ordered receiving/complete lines; partial orders do not enter its numerator.

## Task 1: Regression and Repair

- [x] Add `backend/tests/purchase_overview_export_contract.py`: execute `overview_batches` against the real accounting fixture through an adapter enforcing SQL Server's unique final ORDER BY fields; cover project code, completion rate and line count in both directions.
- [x] Run `env PYTHONPATH=backend/.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 backend/tests/purchase_overview_export_contract.py`; reproduced duplicate final ORDER BY failures in project-code ascending/descending and empty-authorization cases. The legacy `.venv` is Python 3.9; use the launcher's existing Python 3.12 dependencies.
- [x] Add `overview_order(query)` in `backend/app/services/purchase_reader.py`: primary order followed by unique organization/project keys. Use it in `list_overview` and `backend/app/services/report_export_data.py::overview_batches`.
- [x] Run all `purchase*contract.py` (76 tests including the new regression) and `report_export_contract.py` (10 tests): exit 0. Re-run the actual A-202503 query with the existing protected Kingdee read-only connection and the same authorized organizations: one row, organization 499413, 216 request lines, 196 complete, rate 90.740740740740; no production writes or export job changes.
- [x] Review the diff and append verified results to `change.md`, preserving existing entries. `git diff --check` passed.

## Task 2: Approved Metrics and Layout

User confirmed conversion counts only receiving and complete, excluding partial orders. The matching written baseline is `docs/superpowers/specs/2026-10-12-purchase-overview-rates-design.md`.

- [x] Extend relational overview tests: receipt remains 1/9, conversion is 3/9 (not 5/9); partial-only is zero, receiving/complete is 100, review-only is zero. Exercise conversion filters after aggregation, both sort directions, and export equivalence. RED reproduced missing fields/old label; GREEN 78 purchase tests.
- [x] Add frontend migration tests for hidden/moved product line, added conversion column, unchanged widths/sort, preserved unknown preference properties, and once-only migration of personal schemes. Layout RED/GREEN, 3 tests.
- [x] Implement SQL `100.0*(receiving_lines+complete_lines)/total_lines AS conversion_rate`; register aggregate field and sortable query enum, rename the receipt label in `purchase_fields.py`. No database migration.
- [x] Keep `completion_rate` stable. Reuse the existing bar renderer with `params.value` for both rates; use shared sort-field membership. Apply a once-only local layout migration to stored columns and legacy/current personal scheme preferences, not other users.
- [x] Run required UI/style/list/system/archive contracts and build, field/enum contracts, purchase/overview/export/query-v2 tests and browser rate/layout/export behavior; verify the real read-only A-202503 ratios. Purchase78, export11 (actual workbook headers/data), query-v2 38, frontend workspace20/layout3, required contracts and build exit0. Browser1440/1182/390 no page overflow; original hidden product line width137 preserved, old scheme migrated, both rates, conversion sorting and accepted-scope export request pass. Real ERP: one org499413, 216/196/12, 90.740740740740/96.296296296296.
- [x] Update the report explanation and add verified scope to change.md. Review found stale conversion sorting across old schemes; unit and browser RED reproduced, then explicit null sort state and no-sort scheme default restored; browser reload/restore GREEN and build exit0. No production deployment or Git integration.

## Development Service Handoff

Completed on 2026-10-12. The first user launch reused ordinary backend PID5062 without the read-only configuration. After the verified local backend was stopped, the user relaunched the existing read-only entry; PID6413 has the protected purchase configuration, K3_READ_ONLY=true and ERP_SYNC_WORKER_ENABLED=false. Actual signed-in query of A-202503 returns three organization/project rows under the local user's broader scope; the 12-inch Bench row has 216 lines, 90.7% receipt and 96.3% conversion. Actual export job 4f2a79e5 succeeded with three rows and was downloaded. Read-only XLSX validation confirms product line first and both rates matching the list, including underlying precision. Screenshot: outputs/purchase-overview-rates-20261012/live-overview.png. No production release or Git integration.
