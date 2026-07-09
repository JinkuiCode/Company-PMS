import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const projectList = read('src/views/project/ProjectList.vue')

for (const label of [
  '基础信息',
  '阶段进度',
  '计划节点',
  '实际节点',
  '推进记录',
  '产品配置',
  '交付验收',
  '人员分工',
  '问题统计',
  '工期分析',
  '系统信息',
]) {
  assert.match(projectList, new RegExp(label), `Project detail drawer should expose ${label}`)
}

assert.match(
  projectList,
  /sheetDetailGroups/,
  'Project progress drawer should continue to render metadata-backed sheet groups',
)
assert.match(
  projectList,
  /drawerOpenGroups/,
  'Project detail drawer should keep multi-open collapse state instead of a single active tab',
)
assert.match(
  projectList,
  /long_text/,
  'Project detail drawer should treat long text fields as a dedicated layout case',
)
assert.match(
  projectList,
  /progress-summary|maxSummaryLength|24/,
  'Project detail drawer should truncate progress-note summaries to the agreed max length',
)
assert.match(
  projectList,
  /el-tooltip/,
  'Readonly reasons and quick-add affordances should use tooltip-based icon affordances',
)
assert.match(
  projectList,
  /saveSheetDetailField/,
  'Editable total-table fields should have a dedicated save path',
)
assert.match(
  projectList,
  /aria-label/,
  'Drawer edit and quick-add actions should include accessible labels',
)
assert.match(
  projectList,
  /aria-pressed/,
  'Quick-add toggle should expose pressed state for assistive technology',
)
assert.doesNotMatch(
  projectList,
  /drawer-field-grid|grid-template-columns:\s*1fr 1fr/,
  'Project detail drawer should drop the old two-column card grid layout',
)
assert.doesNotMatch(
  projectList,
  /引用只读|自动计算|只读|可编辑/,
  'Project detail drawer should replace readonly/editability text badges with icons and tooltips',
)
assert.doesNotMatch(
  projectList,
  /field === 'product_line'/,
  'Progress page should continue to reject direct edits to archive-derived product line',
)
assert.doesNotMatch(
  projectList,
  /@row-clicked="onProjectRowClicked"/,
  'Single-clicking a project row should not open the detail drawer',
)

console.log('project sheet detail drawer contract passed')
