import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync, existsSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { createRequire } from 'node:module'
import ts from 'typescript'
import * as vue from 'vue'

const require = createRequire(import.meta.url)
const root = resolve(dirname(new URL(import.meta.url).pathname), '../src')
const pages = ['PurchaseOverviewList', 'PurchaseProgressList', 'InventoryList', 'StockDetailList']
const removedFor = name => name === 'InventoryList' ? ['Organization', 'project_name'] : ['project_name']
const sourceFor = name => readFileSync(resolve(root, `views/reports/${name}.vue`), 'utf8')
const field = key => ({ key, label: key, group: 'identity', value_type: 'text', type: 'text', width: 140 })
const fixture = () => ({
  fields: ['project_name', 'project_code', 'product_line_name', 'material_name', 'completion_rate', 'conversion_rate', 'Organization'].map(field),
  overview_fields: ['project_name', 'project_code', 'product_line_name', 'material_name', 'completion_rate', 'conversion_rate'].map(field),
  query_fields: [{ field: 'project_name', label: '项目名称', type: 'text' }],
  organizations: [{ value: 7, label: '产品线 A' }], progress_labels: {}, document_status_labels: {},
  sort_fields: ['bill_date', 'project_code', 'material_name'], default_sort: { sort: 'bill_date', direction: 'asc' },
})

// Run each page's actual setup code, replacing only UI/lifecycle and network boundaries.
function pageHarness(name, initial = {}, userId = 42, response = fixture()) {
  const storage = new Map(), calls = [], warnings = [], cache = new Map()
  const key = `pms:${({ PurchaseOverviewList: 'purchase-overview', PurchaseProgressList: 'purchase-report', InventoryList: 'inventory-report', StockDetailList: 'stock-detail' })[name]}:v1:${userId}`
  storage.set(key, JSON.stringify(initial))
  const localStorage = { getItem: key => storage.get(key) ?? null, setItem: (key, value) => storage.set(key, value) }
  const metadata = response
  const api = new Proxy({}, { get: (_, key) => async (...args) => {
    calls.push({ method: key, args })
    if (String(key).endsWith('Metadata')) return metadata
    return { items: [], openings: [], orders: [], receipts: [], total: 0, summary: null, queried_at: '', total_lines: 0, complete_lines: 0, review_lines: 0 }
  } })
  function load(path) {
    if (path === 'vue') return { ...vue, onMounted() {}, onUnmounted() {}, watch() {} }
    if (path === 'element-plus') return { ElButton: {}, ElMessage: { warning: value => warnings.push(value) }, ElMessageBox: { confirm: async () => true } }
    if (path === 'ag-grid-community') return { ModuleRegistry: { registerModules() {} }, AllCommunityModule: {} }
    if (path === 'ag-grid-vue3' || path === '@element-plus/icons-vue' || path.endsWith('.vue') || path.endsWith('.css') || path === '@/form-system') return {}
    if (path.startsWith('@/api/')) return api
    if (path === '@/stores/auth') return { useAuthStore: () => ({ user: { id: userId }, hasPermission: () => true }) }
    if (path === '@/query-system/column-grid') return { decorateQueryColumns: value => value }
    if (path === '@/config/listUi') return { DEFAULT_PAGE_SIZE: 50, PMS_GRID_OPTIONS: {}, PMS_ACTION_COLUMN: {} }
    if (path === '@/utils/agGridLocale') return { chineseLocaleText: {} }
    if (!path.startsWith('@/') && !path.startsWith('/')) return require(path)
    let file = path.startsWith('@/') ? resolve(root, path.slice(2)) : path
    if (!existsSync(file)) file += '.ts'
    if (cache.has(file)) return cache.get(file)
    const exports = {}
    cache.set(file, exports)
    const code = ts.transpileModule(readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
    new Function('require', 'exports', 'module', code)(specifier => load(specifier.startsWith('.') ? resolve(dirname(file), specifier) : specifier), exports, { exports })
    return exports
  }
  const script = sourceFor(name).match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1]
  const code = ts.transpileModule(`${script}\nexports.page = { metadata, visible, columns, filterFields, conditions, sort, planSnapshot, submitWorkspace, initialize, read: typeof readPreferences === 'function' ? readPreferences : initialize, save: typeof saveLayout === 'function' ? saveLayout : typeof savePreferences === 'function' ? savePreferences : persist };`, { compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022 } }).outputText
  const exports = {}
  new Function('require', 'exports', 'localStorage', 'defineProps', 'defineEmits', 'defineExpose', code)(specifier => load(specifier.startsWith('.') ? resolve(root, 'views/reports', specifier) : specifier), exports, localStorage, () => ({}), () => () => {}, () => {})
  const page = exports.page
  page.metadata.value = metadata
  return { page, calls, warnings, saved: () => JSON.parse(storage.get(key)), storage, key }
}
const flatten = columns => columns.flatMap(column => column.children ? flatten(column.children) : [column])

for (const name of pages) {
  test(`${name}: guide immediately follows column settings with the approved page key`, () => {
    const page = name.startsWith('Purchase') ? 'purchase' : name === 'InventoryList' ? 'inventory' : 'stock'
    assert.ok(new RegExp(`<PmsListColumnPicker[^]*?/>\\s*<PmsPageGuide page="${page}"\\s*/>`).test(sourceFor(name)), 'guide must immediately follow the column picker')
    assert.match(sourceFor(name), /import PmsPageGuide from '@\/page-guide\/PmsPageGuide.vue'/)
  })

  test(`${name}: default columns remove obsolete identity and start with product line`, async () => {
    const { page } = pageHarness(name)
    await page.initialize()
    const columns = flatten(page.columns.value)
    assert.equal(columns[0].colId, 'product_line_name')
    assert.equal(columns[0].initialPinned, 'left')
    for (const removed of removedFor(name)) assert.ok(!columns.some(column => column.colId === removed))
    if (name.startsWith('Purchase')) {
      assert.ok(!page.filterFields.value.some(field => field.field === 'project_name'))
      assert.equal(typeof page.filterFields.value.find(field => field.field === 'project_code').reference.load, 'function')
      for (const column of columns.filter(column => /_rate$/.test(column.colId))) assert.notEqual(column.initialPinned, 'left')
      assert.doesNotMatch(sourceFor(name).split('<template>')[1], /project_name|项目名称/)
    } else {
      const organization = page.filterFields.value.find(field => /organization_ids?$/.test(field.field))
      assert.match(organization.label, /^产品线/)
      assert.deepEqual(organization.options, [{ value: 7, label: '产品线 A' }])
    }
  })

  test(`${name}: old stored layout migrates once, preserving width, unrelated preferences and plans`, async () => {
    const plans = [{ name: '我的方案', visible: ['project_name', 'material_name'], pageSize: 100 }]
    const { page, saved } = pageHarness(name, { visible: ['project_name', 'Organization', 'project_code', 'material_name'], columns: [
      { colId: 'project_name', sort: 'asc' }, { colId: 'Organization', width: 176 },
      { colId: 'material_name', width: 237, pinned: 'right', sort: 'desc' }, { colId: 'product_line_name', hide: true, width: 163 },
    ], plans, custom: 'keep', sort: { sort: 'project_name', direction: 'asc' } })
    await page.read()
    const snapshot = page.planSnapshot()
    assert.equal(page.visible.value[0], 'product_line_name')
    assert.equal(snapshot.columns[0].colId, 'product_line_name')
    assert.equal(snapshot.columns[0].width, 163)
    assert.equal(snapshot.columns[0].hide, false)
    assert.equal(snapshot.columns[0].pinned, 'left')
    assert.equal(snapshot.columns.find(column => column.colId === 'material_name').width, 237)
    for (const removed of removedFor(name)) {
      assert.ok(!snapshot.visible.includes(removed))
      assert.ok(!snapshot.columns.some(column => column.colId === removed))
    }
    assert.equal(snapshot.reportIdentityVersion, 1)
    page.save()
    assert.equal(saved().reportIdentityVersion, 1)
    assert.notEqual(saved().sort?.sort, 'project_name', 'removed sorting must not remain in the stored layout')
    assert.equal(saved().custom, 'keep')
    assert.deepEqual(saved().plans, plans)
  })

  test(`${name}: version 1 respects hidden product line, reordered columns and empty visible choice`, async () => {
    const initial = { reportIdentityVersion: 1, metricLayoutVersion: 1, visible: ['material_name', 'project_code'], columns: [
      { colId: 'material_name', width: 222, pinned: null }, { colId: 'product_line_name', width: 151, hide: true, pinned: null },
    ] }
    const { page } = pageHarness(name, initial)
    await page.read()
    assert.deepEqual(page.visible.value, initial.visible.filter(key => flatten(page.columns.value).some(column => column.colId === key)))
    assert.equal(page.planSnapshot().columns[0].colId, 'material_name')
    assert.equal(page.planSnapshot().columns[1].hide, true)
    assert.equal(page.planSnapshot().columns[1].pinned, null)
    const empty = pageHarness(name, { ...initial, visible: [] }).page
    await empty.read()
    assert.deepEqual(empty.visible.value, [])
  })

  test(`${name}: old backend metadata cannot prematurely complete or persist identity migration`, async () => {
    const response=fixture()
    response.fields=response.fields.filter(field=>field.key!=='product_line_name')
    response.overview_fields=response.overview_fields.filter(field=>field.key!=='product_line_name')
    const initial={visible:['material_name'],columns:[{colId:'material_name',width:222}],custom:'keep'}
    const {page,saved}=pageHarness(name,initial,42,response)
    await page.read()
    page.save()
    assert.deepEqual(saved(),initial,'旧元数据时不能写入完成标记或丢失列偏好')
    assert.equal(page.planSnapshot().reportIdentityVersion,undefined)
  })

  test(`${name}: applying old and new plan preferences goes through one-time migration`, async () => {
    const { page, warnings } = pageHarness(name)
    await page.initialize()
    if (name === 'StockDetailList') page.conditions.value = [
      { id: 1, field: 'material_name', operator: 'contains', value: '物料 A', valueEnd: null, schemaVersion: 2 },
      { id: 2, field: 'organization_ids', operator: 'reference', value: [7], valueEnd: null, schemaVersion: 2 },
      { id: 3, field: 'bill_date', operator: 'between', value: '2026-10-01', valueEnd: '2026-10-12', schemaVersion: 2 },
    ]
    const old = { visible: ['project_name', 'Organization', 'project_code'], columns: [
      { colId: 'project_name', width: 200 }, { colId: 'Organization', width: 155 }, { colId: 'project_code', width: 187 },
    ], pageSize: 100, sort: { sort: 'project_name', direction: 'desc' } }
    await page.submitWorkspace([], old)
    assert.deepEqual(warnings, [])
    const snapshot = page.planSnapshot()
    assert.equal(snapshot.visible[0], 'product_line_name')
    assert.equal(snapshot.columns[0].colId, 'product_line_name')
    for (const removed of removedFor(name)) assert.ok(!snapshot.visible.includes(removed))
    assert.notEqual(snapshot.sort.sort, 'project_name')
    assert.equal(snapshot.pageSize, 100)
    const modern = { reportIdentityVersion: 1, metricLayoutVersion: 1, visible: ['project_code'], columns: [{ colId: 'project_code', width: 209, pinned: null }] }
    await page.submitWorkspace([], modern)
    assert.deepEqual(page.visible.value, ['project_code'])
    assert.equal(page.planSnapshot().columns[0].width, 209)
    assert.equal(page.planSnapshot().reportIdentityVersion, 1)
  })
}

for (const name of ['InventoryList', 'StockDetailList']) {
  test(`${name}: column state retains flex and multi-sort priority`, async () => {
    const { page } = pageHarness(name, { reportIdentityVersion: 1, visible: ['product_line_name', 'material_name'], columns: [
      { colId: 'material_name', width: 231, flex: 2, sort: 'desc', sortIndex: 1 },
      { colId: 'product_line_name', width: 147, pinned: 'left' },
    ] })
    await page.read()
    assert.equal(page.planSnapshot().columns[0].flex, 2)
    assert.equal(page.planSnapshot().columns[0].sortIndex, 1)
  })
}

for (const name of ['PurchaseOverviewList', 'PurchaseProgressList']) {
  test(`${name}: project code reference still forwards name searches`, async () => {
    const { page, calls } = pageHarness(name)
    await page.initialize()
    const reference = page.filterFields.value.find(field => field.field === 'project_code').reference
    await reference.load({ keyword: '项目名称搜索', page: 1, pageSize: 50, batch: { field: 'name', values: ['项目 A'] } })
    const query = calls.find(call => call.method === 'getPurchaseProjectReference').args[0]
    assert.equal(query.keyword, '项目名称搜索')
    assert.equal(query.batch_field, 'name')
    assert.deepEqual(query.batch_values, ['项目 A'])
  })
}

test('inventory saving preserves a different user and legacy named plans', async () => {
  const one = pageHarness('InventoryList', { plans: [{ name: 'A' }], pageSize: 100 }, 42)
  const two = pageHarness('InventoryList', { plans: [{ name: 'B' }] }, 99)
  await one.page.read(); one.page.save()
  assert.notEqual(one.key, two.key)
  assert.deepEqual(one.saved().plans, [{ name: 'A' }])
  assert.equal(one.saved().pageSize, 100)
  assert.deepEqual(two.saved().plans, [{ name: 'B' }])
})
