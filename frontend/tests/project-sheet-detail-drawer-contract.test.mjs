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
  /drawerGroupSummary\(group\)/,
  'Project detail drawer should show a dedicated summary in the progress-group heading',
)
assert.match(
  projectList,
  /function drawerGroupSummary\([\s\S]*?group\.key !== 'progress'[\s\S]*?summarizeProgressText/,
  'Only the progress-group heading should use the short progress-note summary',
)
assert.match(
  projectList,
  /function summarizeProgressText\([\s\S]*?split\(\/\\r\?\\n\/, 1\)\[0\]/,
  'Progress-group summaries should use only the first line of a multi-line record',
)
const sheetValueFormatter = projectList.match(/function formatSheetFieldValue\([\s\S]*?\n}\n\nfunction startSheetFieldEdit/)
assert.ok(sheetValueFormatter, 'Project detail drawer should keep field-value formatting in a dedicated helper')
assert.doesNotMatch(
  sheetValueFormatter[0],
  /summarizeProgressText/,
  'Drawer value rows, including long text progress notes, should render their full values',
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
const readonlyReasonControl = projectList.match(/<button[\s\S]*?class="drawer-field-reason"[\s\S]*?<\/button>/)
assert.ok(readonlyReasonControl, 'Readonly source reasons should use native keyboard-focusable buttons')
assert.match(
  readonlyReasonControl[0],
  /:aria-label="`\$\{field\.label}：\$\{drawerFieldReason\(field\)!\.tooltip\}`"/,
  'Readonly source buttons should include an explicit screen-reader label',
)
assert.match(
  readonlyReasonControl[0],
  /<el-icon aria-hidden="true">/,
  'Readonly source button icons should be decorative for assistive technology',
)
assert.match(
  projectList,
  /\.drawer-field-reason \{[\s\S]*?position: absolute;/,
  'Readonly source controls should not consume drawer field layout space',
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
