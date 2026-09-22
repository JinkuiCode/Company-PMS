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

### Task 5: Approved production release and initial import

The user explicitly approved the production upgrade/import on 2026-09-17 after supplying a manual backup and accepting recovery responsibility. Do not repeat this approval request. Any credential entry is a technical handoff only.

- [x] Verify the backup identity. The original full backup is PMS dated 2026-09-17 16:49:11; it has no backup checksum. An additional copy-only backup with checksum was created at `E:\PMS-bakup\PMS-preimport-20260917-173045.bak`, and `RESTORE VERIFYONLY WITH CHECKSUM` succeeded.
- [x] Build and stage release `d300b413c69a4c3f22c2f5b6c4e68dffde1e2977`; verify ZIP and staged file hashes. No GitHub push or master merge is included in this step.
- [x] Generate formal server-local preflight: 937 source, 936 ready, 643 blank names, one excluded `PMS-ACCEPT-20260914-001` conflict.
- [x] Capture existing 4 archives / 1 project and create program backup at `C:\PMS\.runtime\release-history\20260917\pre-initial-import\PMS-operations-20260917-174625`.
- [x] Execute the approved database upgrade and import using a separately entered upgrade identity. Remote output confirms `database-upgrade_OK`, `runtime-schema_OK`, `initial-import_OK` and `import-verification_OK`.
- [x] Verify all imported names against source Remarks, unchanged existing archives, 936 import logs, unchanged ERP log count and schema readiness through `verify.py`. Independently request the production health endpoint (HTTP 200, status ok) and compare the served index with the local release index; they match.
- [ ] Inspect the final deployment receipt and final server Git cleanliness when remote window interaction is available. The observed console ends at `import-verification_OK`; do not repeat the import. GitHub push and master merge are not part of this execution.
