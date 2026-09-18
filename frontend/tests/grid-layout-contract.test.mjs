import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const read = p => readFileSync(new URL('../src/' + p, import.meta.url), 'utf8')
const editor = read('components/PmsGridLayoutEditor.vue')
for (const term of ['左侧冻结', '中间滚动', '右侧冻结', '列宽', 'draggable', '未显示字段']) assert.ok(editor.includes(term), term)
const picker = read('components/PmsListColumnPicker.vue')
assert.match(picker, /applyColumnState/)
assert.match(picker, /async function save/)
assert.doesNotMatch(picker, /PmsSegmentedControl|activeTab/)
assert.doesNotMatch(editor, /applyColumnState|调整自动保存/)
for (const page of ['ProjectArchive', 'ProjectList']) assert.match(read('views/project/' + page + '.vue'), /:get-grid-api=/)
assert.doesNotMatch(read('views/project/ProjectList.vue'), /marryChildren: true/)
assert.match(read('styles/pms-theme.css'), /1px solid var\(--pms-frozen-divider\)/)
console.log('grid layout contract passed')
