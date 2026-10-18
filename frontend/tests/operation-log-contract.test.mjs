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
assert.match(view, /PmsQueryWorkspace entry-mode="document"/, '操作日志应复用已批准的统一单据查询工作区')
assert.match(view, /\/operation-logs/, '页面应调用操作日志查询接口')
assert.match(view, /operation-audit-detail[\s\S]*?role="dialog"/, '详情应使用已批准的侧边审计布局')
assert.match(view, /diff_data|diffData/, '详情需要展示字段差异')
assert.match(view, /diff_items/, '详情应优先消费后端生成的可读差异项')
assert.match(view, /field_label/, '差异项应以中文字段名作为主要标识')
assert.match(view, /field_key/, '差异项应保留原始字段编码供技术排查')
assert.match(view, /audit-diff[\s\S]*?overflow-wrap:\s*anywhere/, '变更前后值应使用可换行的业务值样式')
assert.match(view, /before_display/, '主要业务值必须消费后端可读投影')
assert.match(view, /after_display/, '主要业务值必须消费后端可读投影')
assert.match(view, /module/, '筛选应包含模块')
assert.match(view, /action/, '筛选应包含动作')
assert.match(view, /status/, '筛选应包含状态')
assert.match(view, /field:\s*'entity_name'/, '对象名称应使用独立业务字段查询')
assert.match(view, /field:\s*'operator_name'/, '操作者应使用独立业务字段查询')
assert.doesNotMatch(view, /field:\s*'keyword'/, '不重新引入已取消的综合关键词查询')

console.log('operation-log contract passed')
