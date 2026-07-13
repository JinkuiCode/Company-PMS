import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const projectList = read('src/views/project/ProjectList.vue')
const columnPicker = read('src/components/PmsListColumnPicker.vue')

assert.match(
  columnPicker,
  /字段搜索|搜索字段/,
  'Column picker should support searching sheet fields',
)
assert.match(
  columnPicker,
  /恢复默认/,
  'Column picker should let users restore the agreed default selection',
)
assert.match(
  columnPicker,
  /已选/,
  'Column picker should show the selected dynamic-column count',
)
assert.match(
  columnPicker,
  /list_available/,
  'Column picker should only allow list-available fields to be toggled into the list',
)
assert.match(
  columnPicker,
  /quick_addable/,
  'Column picker should understand quick-add eligibility separately from list visibility',
)
assert.match(
  projectList,
  /getColumnState|applyColumnState/,
  'Project list should persist and restore AG Grid column state alongside selected fields',
)
assert.match(
  projectList,
  /selected_sheet_field_keys/,
  'Project list column preferences should serialize selected dynamic field keys explicitly',
)
assert.match(
  projectList,
  /columnState/,
  'Project list column preferences should serialize AG Grid column state explicitly',
)
assert.match(
  projectList,
  /Array\.isArray\(saved\?\.selected_sheet_field_keys\)/,
  'An intentionally empty saved optional-column selection should remain empty after restoration',
)
assert.match(
  projectList,
  /if \(!columnPreferencesReady\.value \|\| !columnPreferenceWritesEnabled\.value\) return/,
  'Preference writes should wait for saved selection and AG Grid state restoration',
)
assert.match(
  projectList,
  /restoreSelectedSheetFieldKeys\(\)[\s\S]*?columnPreferencesReady\.value = true/,
  'Preference initialization should restore selected fields before enabling persistence and data requests',
)
assert.match(
  projectList,
  /const columnPreferenceWritesEnabled = ref\(false\)/,
  'Grid preference writes should stay disabled until saved column state is restored',
)
assert.match(
  projectList,
  /function completeColumnPreferenceRestore\([\s\S]*?if \(!columnPreferencesReady\.value \|\| !gridApi\.value\) return[\s\S]*?restoreColumnState\(\)[\s\S]*?columnPreferenceWritesEnabled\.value = true/,
  'Saved AG Grid state should be applied before preference writes are enabled',
)
assert.match(
  projectList,
  /function handleGridStructureChanged\([\s\S]*?if \(!columnPreferenceWritesEnabled\.value \|\| restoringColumnState\.value\) return/,
  'Initial AG Grid structure events must not persist a default column state before restoration',
)
assert.match(
  projectList,
  /const dynamicFields = sheetFieldMetas\.value\.filter\(field => field\.list_available\)\.map<ListFilterField<ProjectRow>>/,
  'Dynamic filters should only offer fields that the backend can project into the list',
)
assert.match(
  projectList,
  /async function resolveColumnPreferenceOwner\([\s\S]*?authStore\.fetchUser\(\)[\s\S]*?columnPreferenceOwnerId\.value = authStore\.user\?\.id \?\? null/,
  'Column preferences should resolve a stable authenticated user before reading storage',
)
assert.match(
  projectList,
  /function columnPreferenceStorageKey\(\)[\s\S]*?`\$\{COLUMN_STORAGE_KEY\}:\$\{columnPreferenceOwnerId\.value\}`/,
  'Column preferences should use a user-scoped localStorage key',
)
assert.match(
  projectList,
  /await Promise\.all\(\[fetchOptions\(\), fetchSheetFieldMetadata\(\), resolveColumnPreferenceOwner\(\)\]\)/,
  'Preference restoration should wait for the authenticated user identity',
)

console.log('project list column preferences contract passed')
