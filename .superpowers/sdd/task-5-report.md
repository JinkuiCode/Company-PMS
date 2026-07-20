# Task 5 Report: Project Archive List and Read-Only Drawer UI

## Summary

- Date: 2026-07-20
- Branch: `codex/project-archive-edit-drawer`
- Scope: Task 5 frontend lifecycle UI only
- Backend changes: none
- Global theme or shared list component changes: none

Implemented the project archive lifecycle UI on the established `PmsDataList` / AG Grid surface:

- The list defaults to enabled archives and sends `enabled=true`, `enabled=false`, or `enabled=all` explicitly.
- All project archive `archive_status` filter, column, create editor, drawer editor, enum fetch, and payload use were removed.
- Enabled rows expose permission-aware edit, sync, disable, and delete actions.
- Disabled rows expose view, enable, and delete actions; their drawer is read-only, shows an `已禁用` badge, and renders no save or sync footer.
- Delete-protected rows render a disabled delete control with a blocker tooltip. A stale client state may still reach the backend, whose structured `409 detail.message` remains authoritative through the shared request interceptor; the page then refreshes its list state.
- Single and batch enable changes use the lifecycle endpoints guarded by `project:archive:toggle`.
- Batch delete and batch enable/disable send every selected ID in one request and do not pre-filter protected rows.
- Disabled rows are muted while reusing existing PMS color and status tokens.
- Stale AG Grid state is reconciled so fixed columns are visible and pinned, including `archive_actions` on the right. Restoring defaults reapplies the fixed-column state, and the operation column also uses AG Grid visibility/pinning locks.

## RED Evidence

Created `frontend/tests/archive-lifecycle-contract.test.mjs` before changing production code, then ran:

```bash
cd frontend
node tests/archive-lifecycle-contract.test.mjs
```

Result: exit `1` as expected.

First failing assertion:

```text
AssertionError [ERR_ASSERTION]: Project archive list should default to enabled records
```

The failure was caused by the missing `archiveQuery.enabled: true` lifecycle state, not a syntax or test-loading error.

## GREEN Evidence

Ran every command required by the Task 5 brief:

```bash
cd frontend
node tests/archive-lifecycle-contract.test.mjs
node tests/archive-edit-drawer-contract.test.mjs
node tests/archive-filter-contract.test.mjs
node tests/list-standard-contract.test.mjs
node tests/system-ui-consistency-contract.test.mjs
npm run build
```

Results:

```text
archive lifecycle contract passed                exit 0
archive edit drawer contract passed              exit 0
archive filter contract passed                   exit 0
list standard contract passed                    exit 0
system UI consistency contract passed            exit 0
vue-tsc -b && vite build                          exit 0
Vite: 2293 modules transformed; built in 353ms
```

Additional regression checks:

```bash
cd frontend
node tests/list-navigation-polish-contract.test.mjs
node tests/style-contract.test.mjs

cd ..
git diff --check
```

Results:

```text
list navigation polish contract passed           exit 0
style contract passed                            exit 0
git diff --check                                 exit 0
```

The production build emitted the repository's existing Vite warning for chunks larger than 500 kB; it emitted no TypeScript error and completed successfully.

## Exact Files

- Modified: `frontend/src/views/project/ProjectArchive.vue`
- Created: `frontend/tests/archive-lifecycle-contract.test.mjs`
- Created: `.superpowers/sdd/task-5-report.md`

No backend file, `AGENTS.md`, `change.md`, shared component, global theme, or unrelated image was modified.

## Browser-Risk Notes

- No authenticated browser session with representative enabled, disabled, protected, and ERP-pending archives was available for end-to-end interaction testing.
- The contracts verify source behavior and the build verifies Vue/TypeScript integration, but they do not exercise Element Plus's `null` select option or AG Grid local-storage restoration in a real browser.
- The protected-delete explanation uses the native button `title` tooltip so the disabled control remains non-clickable. Its exact hover timing and presentation are browser-dependent.
- The operation column was widened for four enabled-row actions and remains pinned; a manual pass at narrow desktop widths would still be useful to assess density with every permission granted.

## Concerns

- Functional contracts and build are green. Residual risk is limited to the unexecuted authenticated browser scenarios above.
