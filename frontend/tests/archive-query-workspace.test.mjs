import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
const source=readFileSync(new URL('../src/views/project/ProjectArchive.vue',import.meta.url),'utf8')
assert.ok(source.includes('<PmsQueryWorkspace'),'档案使用完整共享方案控件')
assert.ok(!source.includes('<PmsReportPlans'),'不得保留私有保存按钮')
assert.ok(!source.includes('watch([searchKeyword'),'草稿修改不得自动提交')
assert.ok(source.includes('archiveAppliedFilters'),'分页不能查询未提交草稿')
console.log('archive shared query contract passed')
