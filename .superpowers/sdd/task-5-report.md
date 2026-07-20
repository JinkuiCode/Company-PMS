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
- Delete-protected rows render an actual disabled delete button inside a focusable Element Plus tooltip owner. The owner exposes the blocker text through `aria-label` and `aria-disabled`, so mouse, keyboard, and accessible technology can discover why deletion is unavailable.
- Single and batch enable changes use the lifecycle endpoints guarded by `project:archive:toggle`.
- Batch delete and batch enable/disable send every selected ID in one request and do not pre-filter protected rows.
- Disabled rows are muted while reusing existing PMS color and status tokens.
- Stale AG Grid state is reconciled so fixed columns are visible and pinned, including `archive_actions` on the right. Restoring defaults reapplies the fixed-column state, and the operation column also uses AG Grid visibility/pinning locks.
- Drawer save/sync lifecycle `409` responses lock the stale drawer before another submit, retain pending drafts, refresh the same archive with `enabled=all`, and replace `selectedArchive` lifecycle flags without resetting form drafts.

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

Review-fix contracts were then written before the follow-up implementation:

```bash
cd frontend
node tests/archive-lifecycle-contract.test.mjs
node tests/archive-lifecycle-conflict-contract.test.mjs
```

Results: both exited `1` for the intended missing behavior.

```text
Protected deletion should use a focusable accessible tooltip owner around a disabled button
Archive drawer should track a lifecycle conflict independently from draft state
```

The corrected `archive-filter-contract.test.mjs` already passed because the enabled filter implementation existed; the change removed its false-positive plain `status` assertion.

## GREEN Evidence

Ran every command required by the Task 5 brief:

```bash
cd frontend
node tests/archive-lifecycle-contract.test.mjs
node tests/archive-lifecycle-conflict-contract.test.mjs
node tests/archive-edit-drawer-contract.test.mjs
node tests/archive-filter-contract.test.mjs
node tests/list-standard-contract.test.mjs
node tests/system-ui-consistency-contract.test.mjs
npm run build
```

Results:

```text
archive lifecycle contract passed                exit 0
archive lifecycle conflict contract passed       exit 0
archive edit drawer contract passed              exit 0
archive filter contract passed                   exit 0
list standard contract passed                    exit 0
system UI consistency contract passed            exit 0
vue-tsc -b && vite build                          exit 0
Vite: 2293 modules transformed; built in 376ms
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
- Created: `frontend/tests/archive-lifecycle-conflict-contract.test.mjs`
- Modified: `frontend/tests/archive-filter-contract.test.mjs`
- Modified: `change.md`
- Created and updated: `.superpowers/sdd/task-5-report.md`

No backend file, `AGENTS.md`, shared component, global theme, or unrelated image was modified.

## Browser-Risk Notes

- No authenticated browser session with representative enabled, disabled, protected, and ERP-pending archives was available for end-to-end interaction testing.
- The contracts verify source behavior and the build verifies Vue/TypeScript integration, but they do not exercise Element Plus's `null` select option, focus-triggered tooltip behavior, or AG Grid local-storage restoration in a real browser.
- The blocker owner now has mouse/focus tooltip triggers and an accessible label while the nested delete button remains disabled; browser and assistive-technology interaction remains for Task 6 acceptance testing.
- The operation column was widened for four enabled-row actions and remains pinned; a manual pass at narrow desktop widths would still be useful to assess density with every permission granted.

## Concerns

- Functional contracts and build are green. Residual risk is limited to the unexecuted authenticated browser scenarios above.
