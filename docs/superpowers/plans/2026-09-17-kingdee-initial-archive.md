# Kingdee Initial Archive Import Implementation Plan

> **For agentic workers:** Use the executing-plans skill task by task. Production schema changes and data writes require a verified manual backup and separate approval.

**Goal:** Safely stage historical Kingdee sales-project archives in PMS without substituting Kingdee name or code for a missing PMS project name.

**Architecture:** Store archive provenance in `pms_project_archive.data_origin`; represent an absent historical PMS name as SQL `NULL`. Keep ordinary creation and every subsequent archive edit strict. A separate import script first produces a local-to-server exception report, then imports only validated rows when explicitly invoked after approval.

**Tech Stack:** FastAPI, SQLAlchemy, MSSQL 2017, SQLite for tests, Vue 3, TypeScript.

## Global Constraints

- Source query: `[10.10.1.248].[AIS20231211221516].[dbo].[YD_JIN_SALL_ASSISTANTDATA]`, `TypeCode = 'xsxm'`.
- `ProjectCode` maps to PMS project number. Only `Remarks` maps to PMS project name; `ProjectName` is never a PMS-name fallback.
- Import must not call the Kingdee write API or assert a PMS sync time/user.
- Duplicate project codes and existing PMS code conflicts go to an exception report, never silently resolved. Repeated project names (Kingdee remarks) are valid business data, including names already used by another PMS archive.
- Production database backup, upgrade, and import are separate stages. The user approved importing code-distinct candidates and skipping the existing test-code conflict after verification; production upgrade and write still require a verified manual backup and the project-specific maintenance approval.

### Task 1: Archive schema and runtime rules

**Files:** `backend/app/models/project.py`, `backend/app/schemas/project.py`, `backend/app/services/project.py`, `backend/app/services/project_archive_initial_migration.py`, `backend/app/models/init_db.py`, `backend/app/services/database_revision.py`, `backend/tests/kingdee_initial_archive_contract.py`.

- [x] Test that a historical archive may have a null name, while ordinary create cannot.
- [x] Test that editing any field of a nameless archive fails until the name is supplied, and that ERP sync/progress creation is likewise blocked.
- [x] Test provenance and the database migration on a legacy SQLite database.
- [x] Implement nullable name/key, immutable `data_origin`, and a versioned upgrade path; remove legacy name uniqueness while preserving code and serial-number uniqueness.

### Task 2: Read-only preflight and controlled import

**Files:** `backend/app/services/kingdee_initial_archive.py`, `backend/scripts/import_kingdee_initial_archives.py`, `backend/tests/kingdee_initial_archive_contract.py`.

- [x] Test source mapping, blank names, duplicate codes, allowed duplicate names, existing PMS code conflicts, and idempotent reruns with in-memory rows.
- [x] Implement a dry-run report that remains on the server; no full source export to the Mac.
- [x] Implement a separately gated apply path that runs only after verified backup and explicit production-write approval.

### Task 3: Archive UI and field catalog

**Files:** `frontend/src/views/project/ProjectArchive.vue`, `backend/app/services/field_catalog.py`, `backend/app/services/field_policy.py`, frontend archive contract tests.

- [x] Test the historical provenance label and blank-name treatment in list and drawer.
- [x] Show `data_origin` read-only; require a name on edit without changing normal creation behavior.
- [x] Keep existing typography, tokens, and standard list layout.

### Task 4: Verification and handoff

**Files:** `change.md`, this plan, server-only exception report.

- [x] Run focused backend contracts, project archive and database upgrade tests.
- [x] Run frontend archive contracts, mandatory style/list/system checks, and `npm run build`.
- [x] Review code diff and report preflight anomaly totals; do not deploy, merge, or write production data.

The `--apply` path is implemented but remains unexecuted. A server-only code-based diagnostic finds 936 candidates and one existing test-code conflict in the filtered source view; it is not an approved import fingerprint. The production database backup, upgrade, formal preflight, and import remain separate stages.
