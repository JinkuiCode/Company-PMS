import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
import ts from 'typescript'
import { parse } from '@vue/compiler-sfc'

const view = readFileSync(new URL('../src/views/project/ProjectArchive.vue', import.meta.url), 'utf8')
const script = view.match(/<script setup lang="ts">([\s\S]*?)<\/script>/)[1]
const ast = ts.createSourceFile('archive.ts', script, ts.ScriptTarget.Latest, true, ts.ScriptKind.TS)
test('archive template remains valid', () => assert.deepEqual(parse(view).errors, []))
test('detailed address uses unified long text controls; create controls lock during save', () => {
  assert.match(view, /key: 'contact_phone', label: '联系人手机'/)
  assert.match(view, /key: 'address_detail', label: '详细地址', value_type: 'long_text'/)
  assert.equal((view.match(/<PmsTextareaControl/g) || []).length, 2)
  const createTemplate = view.slice(view.indexOf('<PmsFormDrawer'), view.indexOf('</PmsFormDrawer>'))
  for (const control of createTemplate.matchAll(/<Pms(?:Text|Textarea|Select|Date)Control[\s\S]*?\/>/g)) {
    assert.match(control[0], /:disabled="archiveCreateSaving \|\|/, 'Every create control must explicitly disable while saving')
  }
})
function functions(names, bindings = {}) {
  const declarations = ast.statements.filter(node => ts.isFunctionDeclaration(node) && names.includes(node.name?.text))
  assert.equal(declarations.length, names.length, `Missing behavior: ${names.join(', ')}`)
  const js = ts.transpileModule(declarations.map(node => node.getText(ast)).join('\n'), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
  return new Function(...Object.keys(bindings), `${js}; return {${names.join(',')}}`)(...Object.values(bindings))
}

test('new fields use shared metadata groups, not default columns', () => {
  for (const key of ['product_line_id', 'contract_signed_date', 'contract_ship_date', 'actual_ship_date', 'warranty_end_date', 'address_province', 'address_city', 'address_detail', 'project_contact', 'contact_phone']) {
    assert.match(view, new RegExp(`key: '${key}'`), `${key} must have a field definition`)
  }
  assert.match(view, /<PmsFormDrawer[^>]*[\s\S]*?title="新增项目档案"/)
  assert.doesNotMatch(view, /<el-dialog/)
  assert.match(view, /fetchDictOptions\('product_line'\)/)
  assert.match(view, /baseArchiveColumnKeys\.filter\(key => !archiveExpansionKeys\.has\(key\)\)/)
})

test('required policy exempts archives created before activation, not new archives', () => {
  const policy = { required: true, required_effective_at: '2026-09-20T00:00:00Z' }
  const { archiveFieldRequired } = functions(['archiveFieldRequired'], {
    archiveFieldPolicy: () => policy, legacyArchiveRequiredFields: new Set(),
  })
  assert.equal(archiveFieldRequired('contract_signed_date'), true)
  assert.equal(archiveFieldRequired('contract_signed_date', '2026-09-19T23:59:59Z'), false)
  assert.equal(archiveFieldRequired('contract_signed_date', '2026-09-20T00:00:00Z'), true)
  policy.required = false
  assert.equal(archiveFieldRequired('contract_signed_date'), false)
})

test('address validation rejects partial addresses and accepts blank or complete', () => {
  const { archiveAddressComplete } = functions(['archiveAddressComplete'])
  assert.equal(archiveAddressComplete({}), true)
  assert.equal(archiveAddressComplete({ address_detail: 'Street' }), false)
  assert.equal(archiveAddressComplete({ address_province: '11', address_city: '1101', address_detail: '  ' }), false)
  assert.equal(archiveAddressComplete({ address_province: '11', address_city: '1101', address_detail: 'Street' }), true)
})

test('address rows progressively appear and depend on their own form values', () => {
  const { archiveAddressFieldVisible } = functions(['archiveAddressFieldVisible'])
  for (const [values, expected] of [[{}, [true, false, false]], [{ address_province: '11' }, [true, true, false]],
    [{ address_province: '11', address_city: '1101' }, [true, true, true]]]) {
    assert.deepEqual(['address_province', 'address_city', 'address_detail'].map(key => archiveAddressFieldVisible(key, values)), expected)
  }
  assert.match(view, /archiveAddressFieldVisible\(field.key, form\)/)
  assert.match(view, /archiveAddressFieldVisible\(field.key, archiveDrawerForm\)/)
})

test('province clears both dependent fields; city clears detail', () => {
  const form = { address_city: '1101', address_detail: 'old' }
  const handlers = functions(['changeArchiveProvince', 'changeArchiveCreateSelect'], {
    form, clearArchiveServerError: () => {}, archiveCreateServerErrors: {},
  })
  const values = { address_city: '1101', address_detail: 'old' }
  handlers.changeArchiveProvince(values)
  assert.deepEqual(values, { address_city: '', address_detail: '' })
  handlers.changeArchiveCreateSelect('address_city')
  assert.equal(form.address_detail, '')
})

test('province change clears city; Escape restores both values and preexisting drafts', () => {
  const archiveDrawerForm = { address_province: '11', address_city: '1101', address_detail: 'old' }
  const archiveEditingField = { value: null }
  const archiveEditSnapshot = { value: {} }
  const archivePendingChanges = { value: { address_city: { value: '1101', originalValue: '1102' } } }
  const handlers = functions(['startArchiveFieldEdit', 'changeArchiveProvince', 'cancelArchiveFieldEdit'], {
    archiveDrawerForm, archiveEditingField, archiveEditSnapshot, archivePendingChanges,
    archiveOriginalValues: { value: { address_province: '11', address_city: '1102' } },
    archiveDrawerReadOnly: { value: false }, archiveDrawerFieldEditable: () => true,
    clearArchiveServerError: () => {}, archiveDrawerServerErrors: {}, commitArchiveFieldEdit: () => {},
  })
  handlers.startArchiveFieldEdit({ key: 'address_province' })
  archiveDrawerForm.address_province = '12'
  handlers.changeArchiveProvince(archiveDrawerForm)
  assert.equal(archiveDrawerForm.address_city, '')
  handlers.cancelArchiveFieldEdit()
  assert.deepEqual(archiveDrawerForm, { address_province: '11', address_city: '1101', address_detail: 'old' })
  assert.deepEqual(archivePendingChanges.value, { address_city: { value: '1101', originalValue: '1102' } })
})

test('province commit includes cleared city in draft payload', () => {
  const archivePendingChanges = { value: {} }
  const archiveEditingField = { value: 'address_province' }
  const handlers = functions(['commitArchiveFieldEdit', 'sameArchiveDrawerValue', 'buildArchiveDrawerPayload'], {
    archivePendingChanges, archiveEditingField,
    archiveDrawerForm: { address_province: '12', address_city: '', address_detail: '' },
    archiveOriginalValues: { value: { address_province: '11', address_city: '1101', address_detail: 'old' } },
    archiveDrawerFieldByKey: key => ({ key }), archiveDrawerFieldEditable: () => true,
    normalizeArchiveDrawerValue: (_field, value) => value,
  })
  handlers.commitArchiveFieldEdit()
  assert.deepEqual(handlers.buildArchiveDrawerPayload(), { address_province: '12', address_city: '', address_detail: '' })
})

test('region formatter uses names and never leaks unknown codes', () => {
  const { archiveRegionLabel } = functions(['archiveRegionLabel'], {
    archiveRegions: { value: [{ value: '11', label: 'Beijing', children: [{ value: '1101', label: 'City' }] }] },
  })
  assert.equal(archiveRegionLabel('address_province', '11'), 'Beijing')
  assert.equal(archiveRegionLabel('address_city', '1101'), 'City')
  assert.equal(archiveRegionLabel('address_city', '999'), '-')
})

test('creation defaults only the authenticated manager; editing preserves the record manager', () => {
  const form = {}
  const bindings = {
    form, formRef: { value: null }, hasPermission: () => true,
    clearArchiveServerErrors: () => {}, archiveCreateServerErrors: {},
    archiveExpansionFields: [{ key: 'product_line_id' }, { key: 'contract_ship_date' }],
    authStore: { user: { id: 42 } }, archiveCreateSnapshot: { value: '' }, dialogVisible: { value: false },
  }
  const { openCreateDialog, archiveDrawerValues, archiveDateValue } = functions(['openCreateDialog', 'archiveDrawerValues', 'archiveDateValue'], bindings)
  openCreateDialog()
  assert.equal(form.manager_id, 42)
  assert.equal(form.product_line_id, null)
  assert.equal(archiveDrawerValues({ manager_id: 17 }).manager_id, 17)
  assert.equal(archiveDateValue('2026-09-20T10:00:00'), '2026-09-20')
})

test('create payload retains new values, strips noneditable fields and sends date-only values', () => {
  const { buildArchiveCreatePayload } = functions(['buildArchiveCreatePayload'], {
    form: { product_line_id: 7, contract_signed_date: '2026-09-20', address_province: '11', contact_phone: '123' },
    archiveExpansionFields: ['product_line_id', 'contract_signed_date', 'address_province', 'contact_phone'].map(key => ({ key })),
    archiveFieldVisible: () => true, archiveFieldEditable: key => key !== 'contact_phone',
  })
  const payload = buildArchiveCreatePayload()
  assert.equal(payload.product_line_id, 7)
  assert.equal(payload.contract_signed_date, '2026-09-20')
  assert.equal(payload.address_province, '11')
  assert.equal('contact_phone' in payload, false)
})

test('province returning to original still counts the cleared city as an unsaved edit', () => {
  const declaration = ast.statements.find(node => ts.isVariableStatement(node) && node.declarationList.declarations.some(item => item.name.getText(ast) === 'archivePendingChangeCount'))
  const js = ts.transpileModule(declaration.getText(ast), { compilerOptions: { target: ts.ScriptTarget.ES2022 } }).outputText
  const count = new Function('computed', 'archivePendingChanges', 'archiveEditingField', 'archiveDrawerFieldByKey', 'normalizeArchiveDrawerValue', 'archiveDrawerForm', 'archiveOriginalValues', 'sameArchiveDrawerValue', `${js}; return archivePendingChangeCount`)(
    fn => fn(), { value: {} }, { value: 'address_province' }, key => ({ key }), (_field, value) => value,
    { address_province: '11', address_city: '' }, { value: { address_province: '11', address_city: '1101' } }, (a, b) => a === b,
  )
  assert.equal(count, 1)
})
