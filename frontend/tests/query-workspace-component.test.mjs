import assert from 'node:assert/strict'
import { readFileSync, existsSync } from 'node:fs'
const file=new URL('../src/query-system/PmsQueryWorkspace.vue',import.meta.url)
assert.ok(existsSync(file),'正式页面必须使用同一个完整查询方案控件')
const source=readFileSync(file,'utf8')
for(const label of ['方案设置','查询','重置','添加条件','默认方案','新建方案','保存方案'])assert.ok(source.includes(label),label)
assert.ok(!source.includes('保存查询方案'),'移除独立保存入口')
assert.ok(source.includes('useAuthStore'),'真实登录用户隔离')
assert.ok(source.includes('validateReferences'),'提交前验证引用范围')
assert.ok(source.includes('@option-select="load"'),'重选当前方案也必须清除临时条件')
const row=readFileSync(new URL('../src/query-system/PmsQueryConditionRow.vue',import.meta.url),'utf8')
assert.ok(row.includes('PmsQueryReference'),'引用使用生产共享选择器')
assert.ok(!row.includes('prototypes'),'正式控件不得依赖样稿模拟数据')
console.log('query workspace component contract passed')
