# Task 3 Follow-up Agent Report

Status: `DONE_WITH_CONCERNS`

Implementation commit: `3c021ac5cf1f98b66302b4d2151d8352e38f5d67`

Follow-up review fix commit: `bfd48177b54424732065aa6a804c4b8ce0645328`

## Files changed

- `backend/app/api/erp.py`
- `backend/app/services/kingdee.py`
- `backend/app/services/project.py`
- `backend/app/services/project_archive_lifecycle.py`
- `backend/tests/project_archive_lifecycle_concurrency_contract.py`
- `.superpowers/sdd/task-3-report.md`
- `.superpowers/sdd/task-3-followup-agent-report.md`

## RED evidence

- Full concurrency contract: exit `1`, `ImportError` for missing `load_archive_lifecycle_rows`.
- Targeted RED run: absent correlated delete `NOT EXISTS`; blocked-log `RuntimeError`; pending edit unexpectedly succeeded; ERP `scope_context` was unsupported; both ambiguous ERP tests ended with the wrong status.
- Real two-session targeted RED run: create/delete, create/disable, and disable/edit lacked lifecycle claims.
- Timestamp claim regression: exit `1` because the SQLite claim changed `updated_at`.

## Tests and results

The following commands all exited `0`:

```sh
cd backend
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_lifecycle_concurrency_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_lifecycle_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_archive_semantic_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/project_update_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/rbac_permission_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 tests/operation_log_contract.py
env PYTHONPATH=.:.venv-deps312 /Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3 -m py_compile app/api/erp.py app/services/kingdee.py app/services/project.py app/services/project_archive_lifecycle.py tests/project_archive_lifecycle_concurrency_contract.py
```

Summary: six contract scripts passed; all changed Python files compiled; no test hung.

## Concerns

- No live MSSQL instance was available; sequential hinted lock acquisition is covered by MSSQL dialect compilation plus per-row ordering assertions, not a live MSSQL race.
- The lifecycle and RBAC scripts emit the existing non-fatal Passlib/bcrypt metadata warning before passing.
- No additional context is needed.

## Follow-up Review Fix

Status: `DONE_WITH_CONCERNS`

### Files changed

- `backend/app/services/kingdee.py`
- `backend/tests/project_archive_lifecycle_concurrency_contract.py`
- `.superpowers/sdd/task-3-report.md`
- `.superpowers/sdd/task-3-followup-agent-report.md`

### RED / baseline evidence

- RED: a real `KingdeeClient` save using an underlying `httpx.Client.post` timeout changed the archive to `failed`; the durable-`pending` assertion failed.
- Baseline GREEN: explicit Kingdee business rejection already remained `failed`.
- Baseline GREEN: new single and batch mutation-boundary tests proved structured `409`, retained archives, retained project references, and batch rollback.
- Baseline GREEN: the strengthened MSSQL query double exercised the actual sequential loader and captured an ascending hinted statement for every ID.

### GREEN results

All six required contract scripts exited `0`, and `py_compile` passed for `app/services/kingdee.py` and `tests/project_archive_lifecycle_concurrency_contract.py`. The concurrency contract passed after exercising the real-client timeout. No test hung.

### Concerns

- No live MSSQL instance was available; actual-loader MSSQL SQL is compiled and asserted, but server lock scheduling is not integration-tested.
- The review's non-required Minor one-sided edit-race coverage remains deferred.
- The existing non-fatal Passlib/bcrypt metadata warning remains; no additional context is needed.
