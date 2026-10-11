import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import ts from 'typescript'
import { cloneQuery } from '../src/query-system/core.ts'
import { reportDefaults, reportPreferences, reportScope, serializeReportConditions, serializeColumnFilters } from '../src/query-system/report-adapter.ts'
import { buildStockDetailQuery } from '../src/views/reports/stockDetailState.ts'

function pageFunctions(name, names) {
  const source = readFileSync(new URL(`../src/views/reports/${name}.vue`, import.meta.url), 'utf8').split('<script setup lang="ts">')[1].split('</script>')[0]
  const ast = ts.createSourceFile(`${name}.ts`, source, ts.ScriptTarget.Latest, true)
  return ast.statements.flatMap(statement => {
    if (ts.isFunctionDeclaration(statement) && names.includes(statement.name?.text)) return [statement.getText(ast)]
    if (ts.isVariableStatement(statement)) return statement.declarationList.declarations.filter(d => names.includes(d.name.getText(ast))).map(d => `const ${d.getText(ast)};`)
    return []
  }).join('\n')
}

for (const name of ['PurchaseOverviewList', 'PurchaseProgressList', 'InventoryList', 'StockDetailList']) {
  test(`${name} query preserves blank default rows while accepted parameters contain only effective conditions`, async () => {
    const stock = name === 'StockDetailList', inventory = name === 'InventoryList'
    const defaults = reportDefaults(stock ? ['material', 'organization_ids', 'bill_date', 'stock_id'] : inventory ? ['keyword', 'organization_id', 'Stock'] : ['keyword', 'organization_ids', 'project_code', 'application_date', 'supplier_name'])
    const rows = defaults.map((d, i) => ({ ...d, id: i + 1 }))
    if (stock) {
      rows[0].value = 'M1'; rows[1].value = [3]; rows[2].operator = 'between'; rows[2].value = '2026-10-01'; rows[2].valueEnd = '2026-10-11'
    } else if (inventory) rows[0].value = 'M1'
    else rows[2].value = [30]
    const original = structuredClone(rows), conditions = { value: rows }, filters = stock ? { conditions: rows, column_filters: [] } : { value: { conditions: rows, column_filters: [] } }
    let accepted
    const context = { cloneQuery, reportPreferences, reportScope, serializeReportConditions, serializeColumnFilters, buildStockDetailQuery,
      conditions, filters, columnFilters: { value: [] }, invalid: { value: '' }, queryInvalid: { value: '' },
      fields: { value: [] }, defaultKeys: { value: [] }, metadata: { value: { fields: [] } }, projectScope: { value: undefined },
      sort: { sort: 'project_code', direction: 'asc' }, sortFields: {}, page: { value: 1 }, pageSize: { value: 50 },
      pendingSize: { value: null }, pendingPageSize: { value: null }, overviewStatus: { value: '' }, visible: { value: [] },
      savedColumns: [], grid: null, restoring: false, nextTick: async () => {}, saveLayout() {}, savePreferences() {}, persist() {},
      ElMessage: { warning: message => assert.fail(message) },
    }
    const names = ['submitWorkspace', ...(stock ? ['buildQuery'] : inventory ? ['buildParams'] : name === 'PurchaseOverviewList' ? ['draft', 'parameters'] : ['draftSnapshot', 'buildParams'])]
    const declarations = ts.transpileModule(pageFunctions(name, names), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
    const factory = new Function(...Object.keys(context), 'query', 'fetchRows', `${declarations}; return { submitWorkspace, build: ${stock ? 'buildQuery' : inventory ? 'buildParams' : name === 'PurchaseOverviewList' ? 'parameters, draft' : 'buildParams, draft: draftSnapshot'} }`)
    let page
    const submit = async () => {
      accepted = stock ? page.build(filters, 1, 50) : inventory ? page.build(filters.value, 1) : name === 'PurchaseOverviewList' ? page.build({ draft: page.draft(), status: '' }, true) : page.build(page.draft(), true)
    }
    page = factory(...Object.values(context), submit, submit)
    const effective = reportScope(stock ? 'stock-detail' : inventory ? 'inventory' : 'purchase', rows)
    // Workspace emits only the active rows; the page's v-model must remain complete.
    const active = rows.filter(c => Array.isArray(c.value) ? c.value.length : c.value != null && c.value !== '')
    await page.submitWorkspace(cloneQuery(active), {})
    assert.deepEqual(conditions.value, original, 'query must not shrink or rewrite the workspace draft')
    assert.deepEqual(JSON.parse(accepted.filters), JSON.parse(serializeReportConditions(effective.conditions)))
    assert.equal(JSON.parse(accepted.filters).some(c => c.value == null || Array.isArray(c.value) && !c.value.length), false)
    assert.equal(accepted.conditions, undefined)
  })
}
