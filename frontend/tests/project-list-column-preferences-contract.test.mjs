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

console.log('project list column preferences contract passed')
