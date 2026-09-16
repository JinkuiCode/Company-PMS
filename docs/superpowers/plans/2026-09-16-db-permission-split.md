# PMS Database Upgrade and Runtime Permission Split Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep schema upgrades out of production service startup so the daily PMS account can lose `db_owner` after a controlled cutover.

**Architecture:** Preserve `init_db()` as the existing upgrade/bootstrap routine. A release-only command runs it and writes a schema revision marker after success. Production startup only reads that marker; development startup keeps the current automatic initialization. The release procedure performs upgrade before starting the new service.

**Tech Stack:** FastAPI, SQLAlchemy, SQLite contract tests, SQL Server 2017, PowerShell.

## Global Constraints

- No production permission change during code development.
- Do not expose credentials in commands, output, files, or Git.
- A failed or missing migration must stop production startup with a clear error.
- Do not change OA, Kingdee, RBAC, or business data behavior.
- Merge/deploy and database grants require their own approval and backup checkpoint.

---

### Task 1: Test the startup boundary

**Files:** `backend/tests/database_upgrade_contract.py`, `backend/main.py`, `backend/app/services/database_revision.py`.

- [x] Write tests for missing, matching, and outdated revision markers against temporary SQLite databases.
- [x] Write a production lifespan test proving `init_db()` is not called and readiness is checked.
- [x] Run the tests and observe the expected failures.
- [x] Add the revision model/service and change production startup to read-only validation.
- [x] Re-run tests until green.

### Task 2: Add the one-time upgrade command

**Files:** `backend/scripts/upgrade_database.py`, `backend/tests/database_upgrade_contract.py`.

- [x] Add a failing subprocess test for an empty SQLite database and repeat execution.
- [x] Implement the command: validate config, call `init_db()`, write the revision only after success, then verify it.
- [x] Confirm a failed upgrade does not mark the database ready.
- [x] Run tests and existing init/legacy-upgrade contracts.

### Task 3: Document production separation

**Files:** `ops/windows/README.md`, `docs/PMS服务器发布与回退说明.md`, `AGENTS.md`, `change.md`.

- [x] Document backup, upgrade, health verification, account scope, and rollback ordering.
- [x] Require a revision bump whenever schema/data initialization changes.
- [x] Run focused backend contracts, release contract, and `git diff --check`.
- [x] Review the branch diff before presenting the production cutover checklist.

### Production Cutover (separate approval)

- [ ] Obtain a verified `COPY_ONLY`/`CHECKSUM` backup and record existing grants.
- [ ] Have the security administrator provide a dedicated PMS upgrade identity through local secure entry.
- [ ] Run the migration with that identity; verify the marker, tables, and key read paths.
- [ ] Grant `pms_app_runtime` the required PMS database DML rights, then remove `db_owner`.
- [ ] Restart only PMS in an approved window; verify OA login, project reads/writes, and ERP read-only check.
- [ ] Restore previous grants and PMS service version if acceptance fails; do not restart SQL Server.
