import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const enumView = readFileSync(resolve(root, 'src/views/system/EnumList.vue'), 'utf8')
const router = readFileSync(resolve(root, 'src/router/index.ts'), 'utf8')
const enumComposable = readFileSync(resolve(root, 'src/composables/useEnumOptions.ts'), 'utf8')
const projectArchive = readFileSync(resolve(root, 'src/views/project/ProjectArchive.vue'), 'utf8')
const projectList = readFileSync(resolve(root, 'src/views/project/ProjectList.vue'), 'utf8')
const projectProgress = readFileSync(resolve(root, 'src/views/project/ProjectProgress.vue'), 'utf8')
const roleList = readFileSync(resolve(root, 'src/views/system/RoleList.vue'), 'utf8')

assert.match(enumView, /枚举管理/)
assert.match(enumView, /reference_count/)
assert.match(enumView, /allow_add/)
assert.match(enumView, /自动选择|selectedDictId|selectFirst/)
assert.doesNotMatch(enumView, /新增分类/)
assert.match(enumView, /loadEnumOptions\(selectedDict\.value\.dict_code, true\)/)
assert.match(enumView, /产品线存储值不能包含逗号/)

assert.match(router, /path:\s*['"]system\/enum['"]/)
assert.match(router, /EnumList\.vue/)
assert.match(router, /system:enum:view/)
assert.match(router, /path:\s*['"]system\/field['"][\s\S]*redirect:\s*['"]\/system\/enum['"]/)

assert.match(enumComposable, /all_items/)
assert.match(enumComposable, /label_map/)
assert.match(enumComposable, /loadEnumOptions/)

assert.match(projectArchive, /enumLabel\('product_line'/)
assert.match(projectArchive, /enumLabel\('product_type'/)
assert.match(projectList, /productLineLabelMap/)
assert.match(projectList, /enum_code\?: string \| null/)
assert.match(projectList, /field\.enum_code/)
assert.match(projectList, /escapeHtml\(statusLabel\(params\.value\)\)/)
assert.match(projectProgress, /function escapeHtml/)
assert.match(projectProgress, /escapeHtml\(taskStatusLabelMap\.value\[String\(params\.value\)\] \|\| '-'\)/)
assert.match(roleList, /productLineLabel\(pl\)/)

for (const file of [
  'src/views/project/ProjectArchive.vue',
  'src/views/project/ProjectList.vue',
  'src/views/project/ProjectProgress.vue',
  'src/views/Dashboard.vue',
  'src/views/system/RoleList.vue',
]) {
  const source = readFileSync(resolve(root, file), 'utf8')
  assert.match(source, /useEnumOptions|loadEnumOptions/, `${file} 应使用统一枚举能力`)
}

console.log('enum management contract passed')
