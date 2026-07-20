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
  /const archiveDrawerLifecycleConflict = ref\(false\)/,
  'Archive drawer should track a lifecycle conflict independently from draft state',
)
assert.match(
  archive,
  /const archiveDrawerReadOnly = computed\(\(\) =>[\s\S]*?selectedArchive\.value\?\.is_enabled !== 1[\s\S]*?archiveDrawerLifecycleConflict\.value/,
  'A lifecycle conflict should make the current drawer read-only immediately',
)
assert.match(archive, /'ARCHIVE_DISABLED'/, 'Concurrent disable conflicts should be recognized')
assert.match(archive, /'ARCHIVE_OPERATION_PENDING'/, 'Concurrent pending-operation conflicts should be recognized')
assert.match(archive, /'ARCHIVE_LIFECYCLE_CONFLICT'/, 'Equivalent archive lifecycle conflicts should be recognized')

const snapshot = functionSource('fetchArchiveLifecycleSnapshot')
assert.match(snapshot, /enabled:\s*'all'/, 'Lifecycle reconciliation should read disabled as well as enabled archives')
assert.match(snapshot, /row\.id === archiveId/, 'Lifecycle reconciliation should resolve the same archive ID')

const reconcileSelection = functionSource('reconcileSelectedArchiveLifecycle')
assert.match(
  reconcileSelection,
  /selectedArchive\.value = \{ \.\.\.selectedArchive\.value, \.\.\.row \}/,
  'A refreshed same-ID row should replace stale selectedArchive lifecycle flags',
)
assert.doesNotMatch(
  reconcileSelection,
  /archivePendingChanges\.value\s*=/,
  'Lifecycle reconciliation must preserve the pending draft',
)

const reconcileConflict = functionSource('reconcileArchiveDrawerLifecycleConflict')
assert.match(reconcileConflict, /archiveDrawerLifecycleConflict\.value = true/, 'Lifecycle conflicts should lock the drawer before reconciliation')
assert.match(reconcileConflict, /草稿已保留/, 'Lifecycle conflict feedback should explicitly tell the user that drafts are preserved')
assert.match(reconcileConflict, /fetchArchiveLifecycleSnapshot\(archiveId\)/, 'Lifecycle conflicts should refresh the current archive snapshot')
assert.match(reconcileConflict, /reconcileSelectedArchiveLifecycle\(refreshed\)/, 'Lifecycle conflicts should replace stale selected lifecycle state')
assert.match(reconcileConflict, /await fetchList\(\)/, 'Lifecycle conflicts should refresh the visible list')
assert.doesNotMatch(reconcileConflict, /resetArchiveDrawer|archivePendingChanges\.value\s*=/, 'Conflict refresh must not clear or reset draft state')

const saveDrawer = functionSource('saveArchiveDrawer')
assert.match(
  saveDrawer,
  /reconcileArchiveDrawerLifecycleConflict\(error, archiveId, '保存'\)/,
  'Save conflicts should reconcile lifecycle state before allowing another submission',
)
assert.match(
  saveDrawer,
  /reconcileArchiveDrawerLifecycleConflict\(error, archiveId, '同步'\)/,
  'Sync conflicts should reconcile lifecycle state before allowing another submission',
)

const openDrawer = functionSource('openArchiveDrawer')
assert.match(
  openDrawer,
  /selectedArchive\.value\?\.id === row\.id[\s\S]*?reconcileSelectedArchiveLifecycle\(row\)/,
  'Opening a refreshed same-ID row should reconcile it instead of returning with stale lifecycle flags',
)

console.log('archive lifecycle conflict contract passed')
