import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const archive = readFileSync(new URL('../src/views/project/ProjectArchive.vue', import.meta.url), 'utf8')
const formTokens = readFileSync(new URL('../src/form-system/form-tokens.css', import.meta.url), 'utf8')

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
  /<PmsInlineField[\s\S]*?@edit-request="startArchiveFieldEdit\(field\)"/,
  'Only the explicit field-value control should enter field edit mode',
)
assert.doesNotMatch(
  archive,
  /class="archive-drawer-field-(row|label)"[^>]*@click/,
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
  (archive.match(/@keydown\.esc\.stop\.prevent="cancelArchiveFieldEdit"/g) || []).length >= 3,
  'Each shared editor branch should handle Escape directly instead of relying on a swallowed bubbled event',
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
assert.match(archive, /客户/, 'Project archives should expose the customer field')
assert.match(archive, /产品类别/, 'Project archives should use the product-category label')
assert.match(archive, /设备系列/, 'Project archives should use the equipment-series label')
assert.match(archive, /序列号/, 'Project archives should expose the serial-number field')
assert.doesNotMatch(
  archive,
  /\bproduct_line\b|\bproduct_type\b/,
  'Project archive UI must not retain legacy product-line or product-type API fields',
)
assert.doesNotMatch(
  archive,
  /field\.key === 'project_code'/,
  'Project code should no longer be blocked from drawer editing',
)
assert.match(archive, /\/auth\/product-categories/, 'Product-category scope should use the semantic API route')
assert.match(
  archive,
  /archiveProductCategoryOptions[\s\S]*?value:\s*Number\(item\.value\)/,
  'Configurable business enums should enter archive forms as numeric values',
)
assert.match(
  archive,
  /async function fetchDictOptions[\s\S]*?refreshCells\(\{ columns: \[code\], force: true \}\)/,
  'Loading enum labels should refresh the matching AG Grid column instead of leaving numeric storage values visible',
)
assert.match(
  archive,
  /function enumLabel[\s\S]*?const labelMap = dictLabelMaps\[code\][\s\S]*?if \(!labelMap\) return '-'/,
  'Enum cells should show an empty-state marker instead of leaking numeric storage values before labels load',
)
assert.match(
  archive,
  /onMounted\(async \(\) => \{[\s\S]*?fetchUsers\(\)\.catch[\s\S]*?Promise\.allSettled[\s\S]*?completeArchiveColumnPreferenceRestore\(\)[\s\S]*?handleArchiveSortChanged\(\)[\s\S]*?await fetchList\(\)/,
  'Archive startup should isolate option failures and restore the saved ordering before querying the first page',
)
assert.match(
  archive,
  /ARCHIVE_UNIQUE_CONFLICT[\s\S]*?field_key/,
  'Archive uniqueness conflicts should be routed back to the matching field',
)
for (const component of ['PmsFormField', 'PmsInlineField', 'PmsTextControl', 'PmsSelectControl', 'PmsDateControl']) {
  assert.match(archive, new RegExp(`\\b${component}\\b`), `Project Archive should import ${component}`)
}
assert.match(archive, /from '@\/form-system'/, 'Project Archive should consume the shared form-system entry')
assert.match(
  archive,
  /<PmsFormField[\s\S]*?<PmsTextControl[\s\S]*?<PmsSelectControl[\s\S]*?<PmsDateControl/,
  'Project Archive creation should use shared field and control components',
)
assert.match(
  archive,
  /<PmsInlineField[\s\S]*?<template #display>[\s\S]*?<template #editor>[\s\S]*?<PmsSelectControl[\s\S]*?<PmsDateControl[\s\S]*?<PmsTextControl/,
  'Every drawer field should use the shared inline display and editor contract',
)
assert.match(
  archive,
  /const legacyArchiveRequiredFields = new Set[\s\S]*?archiveFieldRequired[\s\S]*?legacyArchiveRequiredFields\.has\(fieldKey\)/,
  'Required markers should fall back with validation rules when field metadata is unavailable',
)
assert.ok(
  (archive.match(/:aria-label="field\.label"/g) || []).length >= 3,
  'Every drawer editor type should expose the field label as its accessible name',
)
assert.match(
  archive,
  /<PmsInlineField[\s\S]*?:error="archiveDrawerServerErrors\[field\.key\]"/,
  'Server validation errors should enter the shared inline field state',
)
assert.ok(
  (archive.match(/:error="archiveDrawerServerErrors\[field\.key\]"/g) || []).length >= 4,
  'Server validation errors should reach the inline field and each shared editor type',
)
assert.doesNotMatch(archive, /pms-inline-field-editor|archive-drawer-field-editor\s+:deep\(\.el-/)
assert.match(
  formTokens,
  /\.pms-form-control \.el-select__wrapper[\s\S]*?background:\s*transparent;[\s\S]*?box-shadow:\s*none;/,
  'Inline drawer selects should not render a second bordered box inside the field row',
)
assert.match(
  formTokens,
  /\.pms-form-control :is\(input, textarea, button\):focus-visible[\s\S]*?outline:\s*none;/,
  'Shared controls should suppress nested focus outlines',
)

console.log('archive edit drawer contract passed')
