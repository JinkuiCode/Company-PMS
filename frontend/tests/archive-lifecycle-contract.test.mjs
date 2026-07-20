import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const archive = readFileSync(new URL('../src/views/project/ProjectArchive.vue', import.meta.url), 'utf8')

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
  /\/projects\/archives\/\$\{[^}]+\}\/enabled/,
  'Single-row lifecycle actions should use the enabled endpoint',
)
assert.match(archive, /\/projects\/archives\/batch-enabled/, 'Batch lifecycle actions should use one batch endpoint')
assert.match(archive, /\/projects\/archives\/batch-delete/, 'Batch delete should use one batch endpoint')
assert.doesNotMatch(
  archive,
  /for\s*\([^)]*selectedRows[\s\S]*?request\.delete/,
  'Batch delete must not loop over single-row delete requests',
)

assert.match(archive, /archiveDrawerReadOnly/, 'Disabled archives should open in a read-only drawer')
assert.match(
  archive,
  /const archiveDrawerReadOnly = computed\(\(\) => selectedArchive\.value\?\.is_enabled !== 1\)/,
  'Archive drawer read-only state should follow is_enabled',
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
assert.match(archive, /delete_blockers/, 'Delete protection should consume backend blockers')
assert.match(archive, /formatDeleteBlockers/, 'Delete blockers should be formatted for a visible tooltip')
assert.match(
  archive,
  /archive-delete-disabled[\s\S]*?disabled/,
  'Protected row deletion should render as a disabled non-clickable control',
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
