# Task 3 Report: Project, Delete, Batch, and ERP Enforcement

Date: 2026-07-17
Baseline: `331004399b7929879ff562f72771672215f1048a`

## TDD Evidence

- RED: extended `backend/tests/project_archive_lifecycle_contract.py` first, then ran:

  ```sh
  cd backend
  env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_lifecycle_contract.py
  ```

  Exit code `1`, expected failure: `ImportError: cannot import name 'batch_change_archives_enabled' from 'app.services.project'`.

- GREEN: implemented the minimal service, schema, API, and ERP integration, then reran the same command. Exit code `0`; key output: `project archive lifecycle contract passed`.

## Coverage Added

- Enabled-only archive options; enabled `true`, `false`, and `None` archive lists; list-level delete guard projection and one guard batch per page.
- Disabled archive rejection for project creation, archive editing, single ERP sync before `pending`, and batch ERP sync without constructing a Kingdee client.
- Structured single-delete `409`, persistent failed delete logs, protected two-item atomic batch deletion, and one-commit successful batch deletion.
- Pending archive atomic batch-disable rejection, product-category data-scope rejection without state changes, and authenticated static batch route permission checks.

## Regression Commands

All commands used this environment prefix and exited `0`:

```sh
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_lifecycle_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_semantic_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_update_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/rbac_permission_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/operation_log_contract.py
```

Key outputs: all five contract scripts printed `... contract passed`. The RBAC run also emitted the existing non-fatal `bcrypt.__about__` version-read warning before passing.

## Transaction and Permission Review

- `batch_delete_archives` and `batch_change_archives_enabled` load the complete in-scope ID set first; protected, pending, missing, or out-of-scope records prevent any target archive mutation. Successful batches call `db.commit()` once and do not loop through `set_archive_enabled`.
- Blocked single and batch deletion write failed operation logs with `commit=True` before returning structured `409` responses. Archive list guards are calculated once for the current page only.
- Single archive changes use `ensure_archive_access`; batch changes share `_apply_archive_scope`, retaining data scope and product-category checks. Batch delete uses `project:archive:delete`; single and batch enable/disable use `project:archive:toggle`. Static `/archives/batch-*` routes precede `/archives/{archive_id}`.

## Changed Files

- `backend/app/api/projects.py`
- `backend/app/schemas/project.py`
- `backend/app/services/project.py`
- `backend/app/services/kingdee.py`
- `backend/tests/project_archive_lifecycle_contract.py`

## Concerns

- Permission node initialization for `project:archive:toggle` remains intentionally deferred to Task 4; this task only enforces the route code.
- The existing RBAC bcrypt metadata warning was observed but does not fail the regression script.

## 2026-07-20 Critical / Important Review Fixes

Implementation commit: `413c1cf` (`Harden project archive lifecycle concurrency`)

### RED evidence

Added `backend/tests/project_archive_lifecycle_concurrency_contract.py` before changing production code and confirmed the following independent failures against `b67a530`:

- `enabled=all` returned HTTP `422` instead of the requested all-record projection.
- Single delete, batch delete, single toggle, and batch toggle did not call `rollback()` when `commit()` failed.
- Batch lifecycle changes processed reversed input order instead of fixed ascending archive ID order.
- The MSSQL lifecycle query helper did not exist, so no compiled `UPDLOCK/ROWLOCK/HOLDLOCK` contract could be satisfied.
- In real two-session SQLite races, an uncommitted winning delete or disable still allowed ERP client construction and external execution.
- Locking precondition failures and idempotent no-op paths left the SQLAlchemy transaction open.

### Implemented fixes

- Added one lifecycle lock query builder that sorts archive IDs and emits the explicit MSSQL table hint `WITH (UPDLOCK, ROWLOCK, HOLDLOCK)`. `with_for_update()` remains only a supplementary hint for other supporting dialects.
- Added SQLite-safe conditional mutations: ERP must conditionally set and commit `pending` before client construction; delete and disable use immediate conditional `DELETE/UPDATE` statements and verify affected-row counts.
- Single and batch delete now lock, recompute blockers in the same transaction, conditionally delete, preserve failed blocked logs, and roll back on every commit failure.
- Single and batch enable/disable now use the same lock order and conditional update protocol; failed, blocked, and no-op paths release their transactions promptly.
- Added explicit archive-list HTTP filtering: omitted/`true`, `false`, and `all`; unsupported values return structured `422` with `ARCHIVE_ENABLED_FILTER_INVALID`.
- Preserved data-scope and product-category filtering by applying the existing scoped query before lifecycle locks. Missing and out-of-scope IDs still share the same generic `404`.

### Verification

All commands exited `0`:

```sh
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_lifecycle_concurrency_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_lifecycle_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_semantic_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_update_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/rbac_permission_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/operation_log_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m py_compile app/api/projects.py app/services/kingdee.py app/services/project.py app/services/project_archive_lifecycle.py tests/project_archive_lifecycle_concurrency_contract.py
```

The new contract uses real SQLite sessions and threads for both winner directions, a route-level `TestClient` contract for the three-state filter, behavior assertions for rollback and batch ordering, and an MSSQL-dialect compilation assertion for the actual table hint.

### Remaining risks

- The MSSQL lock SQL is dialect-compiled and asserted locally, but this machine has no live MSSQL instance for a true concurrent integration run. Production staging should run one delete/sync and disable/sync collision smoke test before release.
- ERP batch sync remains an intentional sequence of independent external operations; it cannot be atomic across Kingdee calls. Each archive does, however, acquire and commit its own conditional `pending` claim before the corresponding external request.

## 2026-07-20 Follow-up Concurrency Closure

Implementation commit: `3c021ac5cf1f98b66302b4d2151d8352e38f5d67` (`Close project archive lifecycle race windows`)

### RED evidence

Extended `backend/tests/project_archive_lifecycle_concurrency_contract.py` before production edits. The first full run exited `1` because `load_archive_lifecycle_rows` did not exist. Independent targeted RED runs then confirmed:

- Delete SQL had no correlated `NOT EXISTS` project-reference guard.
- A failed blocked-delete log raised `RuntimeError: log failed` instead of the lifecycle `409`.
- Editing a `pending` archive succeeded.
- ERP sync rejected the new `scope_context` argument, proving the claim was still unscoped.
- Network ambiguity and external success followed by local commit failure both ended as deletable `failed` rather than durable `pending`.
- Real two-session create/delete, create/disable, and disable/edit races lacked archive write claims; the edit race failed with `档案编辑未声明生命周期`.
- A focused timestamp test exited `1` because the initial SQLite no-op claim implicitly changed `updated_at`.

### Implemented fixes

- Added SQLite conditional no-op lifecycle claims that preserve `updated_at`, and held them through project creation, archive editing, delete, and enable/disable commits.
- Added per-row ascending lifecycle lock acquisition; every MSSQL row query retains `WITH (UPDLOCK, ROWLOCK, HOLDLOCK)` instead of relying on one `IN (...) ORDER BY` query.
- Added correlated project `NOT EXISTS` predicates to single and batch archive deletion mutations.
- Made blocked-delete operation logging best-effort: log failures roll back the session but never replace the structured `ARCHIVE_DELETE_BLOCKED` response.
- Moved archive edit enabled/pending checks into the lifecycle claim transaction and revalidated all edit rules against the claimed row.
- Moved ERP data-scope, manager-scope, product-category scope, and field-policy validation into the pending claim transaction. All post-claim exception reloads use the same scoped query.
- Preserved durable `pending` after save-request network ambiguity, external success with local success-commit failure, and unknown post-save finalization failures. Clearly negative save responses retain existing `failed` behavior.

### Changed files

- `backend/app/api/erp.py`
- `backend/app/services/kingdee.py`
- `backend/app/services/project.py`
- `backend/app/services/project_archive_lifecycle.py`
- `backend/tests/project_archive_lifecycle_concurrency_contract.py`
- `.superpowers/sdd/task-3-report.md`
- `.superpowers/sdd/task-3-followup-agent-report.md`

### GREEN verification

All commands exited `0` on the final implementation:

```sh
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_lifecycle_concurrency_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_lifecycle_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_semantic_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_update_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/rbac_permission_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/operation_log_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m py_compile app/api/erp.py app/services/kingdee.py app/services/project.py app/services/project_archive_lifecycle.py tests/project_archive_lifecycle_concurrency_contract.py
```

Key outputs were the six expected `... contract passed` lines; `py_compile` produced no output. No test hung. The lifecycle and RBAC scripts emitted the pre-existing non-fatal Passlib warning that `bcrypt` has no `__about__` attribute.

### Remaining risks

- MSSQL lock SQL and acquisition order are dialect-compiled/behaviorally asserted, but no live MSSQL instance was available for a real two-session integration race.
- The existing Passlib/bcrypt metadata warning remains outside this task's scope; both affected contracts exited `0`.

## 2026-07-20 Follow-up Review Critical / Important Fixes

Implementation commit: `bfd48177b54424732065aa6a804c4b8ce0645328` (`Preserve ambiguous Kingdee save outcomes`)

### Test-first evidence

The concurrency contract was changed before production code and the four focused cases were run independently:

- **RED:** the real `KingdeeClient.save_assistant_data()` path used an underlying `httpx.Client.post` timeout, logged `保存辅助资料异常: ERP save response timed out`, and failed the durable-`pending` assertion because the archive became ordinary `failed`.
- **Baseline GREEN:** an explicit Kingdee `ResponseStatus.IsSuccess == false` response remained a clear business rejection with `erp_sync_status == "failed"`.
- **Baseline GREEN:** single and batch delete both returned structured `ARCHIVE_DELETE_BLOCKED` after the guard hook committed a new project reference immediately before the real conditional `DELETE`; all archives and projects remained.
- **Baseline GREEN:** the actual `load_archive_lifecycle_rows()` path emitted one MSSQL-compiled statement per distinct ID in ascending order, and every captured statement contained `WITH (UPDLOCK, ROWLOCK, HOLDLOCK)`.

The two Important findings therefore required stronger behavioral coverage, not a production mutation change. The Critical finding required the Kingdee client correction.

### Implemented correction

- Added `KingdeeSaveOutcomeAmbiguous` as the explicit post-request unknown-outcome signal.
- Once the save `post()` begins, transport, HTTP, JSON decoding, malformed response shape, missing success marker, and unknown marker values now raise the ambiguity signal. The existing sync finalizer retains durable `pending` and deletion protection.
- Only a valid response containing explicit boolean `ResponseStatus.IsSuccess == false` remains an ordinary clear rejection and may transition to `failed`.
- Replaced the SQL-text-only delete test with single and batch mutation-boundary behavior tests.
- Replaced the disconnected MSSQL assertions with compiled capture around the actual sequential loader.

### Changed files

- `backend/app/services/kingdee.py`
- `backend/tests/project_archive_lifecycle_concurrency_contract.py`
- `.superpowers/sdd/task-3-report.md`
- `.superpowers/sdd/task-3-followup-agent-report.md`

### GREEN verification

All commands exited `0`:

```sh
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_lifecycle_concurrency_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_lifecycle_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_semantic_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_update_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/rbac_permission_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/operation_log_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m py_compile app/services/kingdee.py tests/project_archive_lifecycle_concurrency_contract.py
```

The concurrency script intentionally logs the simulated Kingdee timeout before passing. No test hung. The lifecycle and RBAC scripts still emit the pre-existing non-fatal Passlib/bcrypt metadata warning.

### Remaining risks

- No live MSSQL instance was available; the stronger loader test compiles every actual per-ID loader statement with the MSSQL dialect but cannot verify server lock scheduling.
- The review's Minor one-sided archive-edit race coverage remains recorded and intentionally deferred, per the follow-up scope.
- The existing Passlib/bcrypt metadata warning remains outside this task.
