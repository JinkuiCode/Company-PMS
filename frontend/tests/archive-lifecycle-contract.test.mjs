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
  /field:'is_enabled',shown:true,operator:'equals',value:1/,
  'Project archive list should default to enabled records',
)
assert.match(archive, /value:1,label:'启用'/, 'Enabled filter should expose the numeric enabled value')
assert.match(archive, /value:0,label:'已禁用'/, 'Disabled filter should expose the numeric disabled value')
assert.match(
  archive,
  /\/projects\/archives\/list[\s\S]*?enabled:\s*'all'/,
  'Project archive list requests should send the explicit enabled filter',
)

assert.match(archive, /project:archive:toggle/, 'Archive lifecycle controls should use the toggle permission')
assert.match(
  archive,
  /const editable = archiveIsEnabled\(row\) && row.can_edit === true && hasPermission\('project:archive:edit'\)[\s\S]*?editable \? '编辑' : '查看'/,
  'Rows expose edit or view; saves arrange background synchronization',
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
assert.match(archive,/selectedArchive\.edit_reason/,'Read-only drawer displays the backend reason')
assert.match(
  archive,
  /v-if="selectedArchive.can_edit && !archiveDrawerReadOnly"/,
  'Read-only archive drawers should not render a save action',
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
assert.match(archive, /handleBatchDelete/, 'Protected deletion remains available through the batch endpoint')
assert.doesNotMatch(archive, /actions.push\(archiveActionButton\('删除'/, 'Deletion is no longer a row action')
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
