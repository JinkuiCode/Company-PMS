import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const view = readFileSync(resolve(root, 'src/views/system/DataDictionaryList.vue'), 'utf8')
const router = readFileSync(resolve(root, 'src/router/index.ts'), 'utf8')

assert.match(view, /PmsDataList/)
assert.match(view, /from ['"]@\/form-system['"]/, 'Data dictionary filters should use the shared PMS form system')
assert.doesNotMatch(view, /<el-(input|select|checkbox)\b/, 'Data dictionary should not render raw Element Plus filters')
assert.match(view, /\/field-catalog/)
assert.match(view, /field:\s*['"]enum_code['"]/, '通过枚举编码不为空保留仅枚举字段筛选能力')
assert.match(view, /<PmsQueryWorkspace[\s\S]*@query="runQuery"/, '查询与回车使用共享工作区，不再复制旧过滤控件')
assert.match(view, /loadCompleteDataset/, '筛选必须覆盖字段目录全部结果，不只当前页')
assert.match(view, /field_name/)
assert.match(view, /field_code/)
assert.match(view, /pinned:\s*['"]left['"]/)
assert.match(view, /height:\s*100%/)
assert.match(view, /pms-data-list-grid-shell[\s\S]*flex:\s*1/)
assert.doesNotMatch(view, /新增分类|编辑分类|新增字段/)
assert.match(router, /DataDictionaryList\.vue/)
assert.match(router, /permission:\s*['"]system:dict:view['"]/)

console.log('data dictionary contract passed')
