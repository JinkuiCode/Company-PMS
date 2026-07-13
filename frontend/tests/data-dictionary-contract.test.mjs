import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const view = readFileSync(resolve(root, 'src/views/system/DataDictionaryList.vue'), 'utf8')
const router = readFileSync(resolve(root, 'src/router/index.ts'), 'utf8')

assert.match(view, /PmsDataList/)
assert.match(view, /\/field-catalog/)
assert.match(view, /仅枚举字段/)
assert.match(view, /@keyup\.enter="handleFilterChange"/)
assert.match(view, /field_name/)
assert.match(view, /field_code/)
assert.match(view, /pinned:\s*['"]left['"]/)
assert.match(view, /height:\s*calc\(100vh - 88px\)/)
assert.match(view, /pms-data-list-grid-shell[\s\S]*flex:\s*1/)
assert.doesNotMatch(view, /新增分类|编辑分类|新增字段/)
assert.match(router, /DataDictionaryList\.vue/)
assert.match(router, /permission:\s*['"]system:dict:view['"]/)

console.log('data dictionary contract passed')
