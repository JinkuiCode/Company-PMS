import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const names = ['system/UserList','system/RoleList','system/ParameterList','system/FieldPolicyList','system/DataDictionaryList','system/ProductLineList','system/MenuList','system/FieldList','system/EnumList','system/OperationLogList','system/SyncTaskList','project/ProjectList','project/ProjectProgress']
for (const name of names) {
  const source = readFileSync(new URL(`../src/views/${name}.vue`,import.meta.url),'utf8')
  assert.match(source, /PmsQueryWorkspace/, `${name}: 复用正式共享工作区`)
  assert.match(source, /system-adapter/, `${name}: 复用页面查询适配层`)
  assert.match(source, /@query=/, `${name}: 显式提交查询`)
  assert.match(source, /@clear-columns=/, `${name}: 方案切换清理列筛选`)
  assert.doesNotMatch(source, /(?:localStorage|sessionStorage)\.setItem\([^\n]*(?:query|scheme)/i, `${name}: 禁止复制私有方案保存`)
  assert.doesNotMatch(source, /<PmsListFilters\b/, `${name}: 移除旧查询面板`)
}
for (const name of ['UserList','ProductLineList','DataDictionaryList']) {
  const source = readFileSync(new URL(`../src/views/system/${name}.vue`,import.meta.url),'utf8')
  assert.match(source, /loadCompleteDataset/, `${name}: 不能仅查询当前服务端页`)
}
for (const name of ['UserList','RoleList','ParameterList','FieldPolicyList','ProductLineList','MenuList','FieldList','EnumList']) {
  const source = readFileSync(new URL(`../src/views/system/${name}.vue`,import.meta.url),'utf8')
  assert.match(source, /PmsQueryColumnHeader/, `${name}: Element 表格使用共享列查询表头`)
  assert.match(source, /#header/, `${name}: 显式 header slot 接入`)
  assert.match(source, /clearColumns\(\)/, `${name}: 方案切换清理列筛选不是空实现`)
}
for (const name of ['system/DataDictionaryList','project/ProjectList','project/ProjectProgress']) {
  const source = readFileSync(new URL(`../src/views/${name}.vue`,import.meta.url),'utf8')
  assert.match(source, /columnContext\.sort\s*=/, `${name}: 自定义表头须保留排序能力`)
}
const project = readFileSync(new URL('../src/views/project/ProjectList.vue',import.meta.url),'utf8')
assert.match(project, /progressListAccepted/, '项目全量结果校验成功才开放漏斗')
console.log('system-query page migration contracts passed (13 pages including server gates)')
