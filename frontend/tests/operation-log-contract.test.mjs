import { readFileSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'
import assert from 'node:assert/strict'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const viewPath = resolve(root, 'src/views/system/OperationLogList.vue')
assert.equal(existsSync(viewPath), true, '操作日志页面文件必须存在')

const router = read('src/router/index.ts')
const layout = read('src/layout/AppLayout.vue')
const view = read('src/views/system/OperationLogList.vue')

assert.match(router, /path:\s*'system\/operation-log'/, '必须注册 /system/operation-log 路由')
assert.match(router, /OperationLogList/, '路由应指向 OperationLogList')
assert.match(layout, /Document|Tickets|Memo/, '菜单图标映射需要支持操作日志图标')

assert.match(view, /PmsDataList/, '操作日志应复用标准列表外壳')
assert.match(view, /PmsListFilters/, '操作日志应复用标准筛选组件')
assert.match(view, /\/operation-logs/, '页面应调用操作日志查询接口')
assert.match(view, /el-drawer/, '详情应使用抽屉展示')
assert.match(view, /diff_data|diffData/, '详情需要展示字段差异')
assert.match(view, /module/, '筛选应包含模块')
assert.match(view, /action/, '筛选应包含动作')
assert.match(view, /status/, '筛选应包含状态')
assert.match(view, /keyword/, '筛选应包含关键词')

console.log('operation-log contract passed')
