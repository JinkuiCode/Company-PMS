import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const archive = readFileSync(new URL('../src/views/project/ProjectArchive.vue', import.meta.url), 'utf8')

assert.doesNotMatch(
  archive,
  /@row-double-clicked="onRowDoubleClicked"|function onRowDoubleClicked/,
  'Project archive rows must not expose a row-wide edit trigger',
)
assert.match(
  archive,
  /class="archive-edit-drawer"/,
  'Project archive editing should use a right-side drawer',
)
assert.match(
  archive,
  /class="archive-drawer-field-value"[\s\S]*?@click="startArchiveFieldEdit\(field\)"/,
  'Only the explicit field-value control should enter field edit mode',
)
assert.doesNotMatch(
  archive,
  /class="archive-drawer-field-row"[^>]*@click/,
  'Clicking a field row or its whitespace must not enter edit mode',
)
assert.match(
  archive,
  /archivePendingChanges/,
  'Archive drawer edits should remain local drafts until the user saves them',
)
assert.match(
  archive,
  /const archivePendingChangeCount = computed\(\(\) => \{[\s\S]*?archiveEditingField\.value[\s\S]*?normalizeArchiveDrawerValue[\s\S]*?sameArchiveDrawerValue/,
  'The fixed save action should become available while the active input contains an uncommitted change',
)
assert.match(
  archive,
  /class="archive-drawer-savebar"[\s\S]*?保存修改/,
  'Archive drawer should keep its save action in a fixed footer',
)
assert.match(
  archive,
  /保存并同步 ERP/,
  'Users with ERP permission should retain a save-and-sync action',
)
assert.match(
  archive,
  /当前档案有未保存的修改/,
  'Closing an archive drawer with drafts should require confirmation',
)
assert.ok(
  (archive.match(/@keydown\.esc\.stop\.prevent="cancelArchiveFieldEdit"/g) || []).length >= 7,
  'Each Element Plus field editor should handle Escape directly instead of relying on a swallowed bubbled event',
)
assert.match(
  archive,
  /\.project-archive-workbench\s*\{[\s\S]*?height:\s*100%;[\s\S]*?min-height:\s*0;/,
  'Archive workbench should keep list and drawer inside a bounded page layout',
)
assert.match(
  archive,
  /\.archive-edit-drawer\s*\{[\s\S]*?height:\s*100%;[\s\S]*?overflow:\s*hidden;/,
  'Archive drawer should contain overflow within its own column',
)
assert.match(
  archive,
  /\.archive-drawer-body\s*\{[\s\S]*?flex:\s*1 1 auto;[\s\S]*?overflow-y:\s*auto;/,
  'Only archive drawer content should scroll',
)
assert.match(
  archive,
  /<el-dialog[\s\S]*?title="新增项目档案"/,
  'Creating an archive should continue to use the focused creation dialog',
)

console.log('archive edit drawer contract passed')
