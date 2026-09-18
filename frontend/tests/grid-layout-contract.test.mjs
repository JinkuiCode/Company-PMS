import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const read = p => readFileSync(new URL('../src/' + p, import.meta.url), 'utf8')
const editor = read('components/PmsGridLayoutEditor.vue')
for (const term of ['左侧冻结', '中间滚动', '右侧冻结', '列宽', 'applyColumnState', 'draggable']) assert.ok(editor.includes(term), term)
for (const page of ['ProjectArchive', 'ProjectList']) assert.match(read('views/project/' + page + '.vue'), /:get-grid-api=/)
assert.doesNotMatch(read('views/project/ProjectList.vue'), /marryChildren: true/)
assert.match(read('styles/pms-theme.css'), /1px solid var\(--pms-frozen-divider\)/)
console.log('grid layout contract passed')
