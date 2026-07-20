import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const archive = readFileSync(new URL('../src/views/project/ProjectArchive.vue', import.meta.url), 'utf8')

function functionSource(name) {
  const match = archive.match(new RegExp(`(?:async )?function ${name}\\([^\\n]*\\) \\{[\\s\\S]*?^\\}`, 'm'))
  assert.ok(match, `Expected ${name} function to exist`)
  return match[0]
}

assert.match(
  archive,
  /const archiveQuery = reactive\(\{[\s\S]*?enabled:\s*true/,
  'Project archive list should default to enabled records',
)
assert.match(archive, /label:\s*'启用',\s*value:\s*true/, 'Enabled filter should expose the true value')
assert.match(archive, /label:\s*'已禁用',\s*value:\s*false/, 'Disabled filter should expose the false value')
assert.match(archive, /label:\s*'全部',\s*value:\s*null/, 'Enabled filter should expose an explicit all value')
assert.match(
  archive,
  /function archiveEnabledHttpValue[\s\S]*?return 'true'[\s\S]*?return 'false'[\s\S]*?return 'all'/,
  'Enabled list filter should encode true, false and all explicitly for HTTP',
)
assert.match(
  archive,
  /\/projects\/archives\/list[\s\S]*?enabled:\s*archiveEnabledHttpValue\(archiveQuery\.enabled\)/,
  'Project archive list requests should send the explicit enabled filter',
)

assert.match(archive, /project:archive:toggle/, 'Archive lifecycle controls should use the toggle permission')
assert.match(
  archive,
  /if \(archiveIsEnabled\(row\)\)[\s\S]*?project:archive:edit[\s\S]*?project:archive:sync[\s\S]*?project:archive:toggle[\s\S]*?禁用[\s\S]*?else[\s\S]*?查看[\s\S]*?project:archive:toggle[\s\S]*?启用/,
  'Enabled and disabled rows should expose the permission-aware lifecycle action sets',
)
assert.match(
  archive,
  /\/projects\/archives\/\$\{[^}]+\}\/enabled/,
  'Single-row lifecycle actions should use the enabled endpoint',
)
assert.match(archive, /\/projects\/archives\/batch-enabled/, 'Batch lifecycle actions should use one batch endpoint')
assert.match(archive, /\/projects\/archives\/batch-delete/, 'Batch delete should use one batch endpoint')
const batchDelete = functionSource('handleBatchDelete')
assert.equal(
  (batchDelete.match(/request\.post\('\/projects\/archives\/batch-delete'/g) || []).length,
  1,
  'Batch delete should call its backend endpoint exactly once',
)
assert.match(batchDelete, /const archiveIds = selectedRows\.value\.map\(row => row\.id\)/, 'Batch delete should collect every selected ID once')
assert.match(batchDelete, /archive_ids:\s*archiveIds/, 'Batch delete should send the complete selected-ID payload')
assert.doesNotMatch(batchDelete, /request\.delete/, 'Batch delete must not call the single-row delete endpoint')

const batchEnabled = functionSource('handleBatchEnabledChange')
assert.equal(
  (batchEnabled.match(/request\.put\('\/projects\/archives\/batch-enabled'/g) || []).length,
  1,
  'Batch enabled changes should call their backend endpoint exactly once',
)
assert.match(batchEnabled, /const archiveIds = selectedRows\.value\.map\(row => row\.id\)/, 'Batch enabled changes should collect every selected ID once')
assert.match(batchEnabled, /archive_ids:\s*archiveIds,[\s\S]*?enabled,/, 'Batch enabled changes should send IDs and the requested target state together')

assert.match(archive, /archiveDrawerReadOnly/, 'Disabled archives should open in a read-only drawer')
assert.match(
  archive,
  /const archiveDrawerReadOnly = computed\(\(\) => \([\s\S]*?selectedArchive\.value\?\.is_enabled !== 1[\s\S]*?archiveDrawerLifecycleConflict\.value/,
  'Archive drawer read-only state should follow is_enabled and lifecycle conflict state',
)
assert.match(
  archive,
  /archiveDrawerReadOnly[\s\S]*?已禁用/,
  'Read-only archive drawers should show a disabled badge',
)
assert.match(
  archive,
  /v-if="!archiveDrawerReadOnly"[\s\S]*?class="archive-drawer-savebar"/,
  'Read-only archive drawers should not render save or sync actions',
)
assert.match(
  functionSource('startArchiveFieldEdit'),
  /if \(archiveDrawerReadOnly\.value\) return/,
  'Read-only drawers should reject field-edit handlers',
)
assert.match(
  functionSource('saveArchiveDrawer'),
  /!selectedArchive\.value \|\| archiveDrawerReadOnly\.value/,
  'Read-only drawers should reject save and save-sync handlers',
)
assert.match(archive, /delete_blockers/, 'Delete protection should consume backend blockers')
assert.match(archive, /formatDeleteBlockers/, 'Delete blockers should be formatted for a visible tooltip')
assert.match(
  archive,
  /h\(ElTooltip,[\s\S]*?class:\s*'archive-delete-tooltip-owner'[\s\S]*?tabindex:\s*0[\s\S]*?role:\s*'button'[\s\S]*?'aria-disabled':\s*'true'[\s\S]*?'aria-label':\s*`删除不可用：\$\{blockerText\}`[\s\S]*?disabled:\s*true/,
  'Protected deletion should use a focusable accessible tooltip owner around a disabled button',
)
assert.doesNotMatch(
  archive,
  /archive-delete-disabled[^\n]*title=/,
  'Protected delete reasons must not depend on a title attached to the disabled button',
)

assert.match(
  archive,
  /field:\s*'is_enabled',[\s\S]*?headerName:\s*'启用状态'/,
  'Project archive list should expose a narrow enabled-state column',
)
assert.match(
  archive,
  /fixedArchiveColumnKeys\.has\(state\.colId\)[\s\S]*?hide:\s*false[\s\S]*?state\.colId === 'archive_actions' \? 'right' : 'left'/,
  'Restoring stale AG Grid state should force fixed columns visible and pinned',
)
const restoreColumnState = functionSource('restoreArchiveColumnState')
assert.match(
  restoreColumnState,
  /gridApi\.applyColumnState\(\{ state: reconciledState, applyOrder: true \}\)/,
  'Reconciled stale column state should be applied to the live grid',
)
const restoreDefaults = functionSource('restoreArchiveColumnDefaults')
assert.match(restoreDefaults, /resetColumnState/, 'Restoring defaults should first reset AG Grid state')
assert.match(
  restoreDefaults,
  /\{ colId: 'archive_actions', hide: false, pinned: 'right' \}/,
  'Restoring defaults should explicitly recover the fixed operation column',
)
assert.match(
  archive,
  /colId:\s*'archive_actions'[\s\S]*?pinned:\s*'right'[\s\S]*?lockVisible:\s*true/,
  'The archive operation column should remain fixed and visible at runtime',
)

assert.doesNotMatch(archive, /archive_status/, 'Project archive UI must not consume the legacy archive-status enum')
assert.doesNotMatch(archive, /field\.key === 'status'/, 'Project archive drawer must not retain a legacy status editor')
assert.doesNotMatch(
  archive,
  /archiveColumnVisibility\('status'\)|field:\s*'status',\s*headerName:\s*'状态'/,
  'Project archive list must not retain the legacy status column',
)

console.log('archive lifecycle contract passed')
