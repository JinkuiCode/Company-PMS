import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const inline = read('../src/form-system/components/PmsInlineField.vue')
const form = read('../src/form-system/components/PmsFormField.vue')
const grid = read('../src/form-system/ag-grid.ts')
const entry = read('../src/form-system/index.ts')
const tokens = read('../src/form-system/form-tokens.css')

assert.match(inline, /class="pms-inline-field"/)
assert.match(inline, /class="pms-inline-field__value"[\s\S]*@click="emit\('edit-request'\)"/)
assert.doesNotMatch(inline, /class="pms-inline-field"[^>]*@click/)
assert.match(inline, /<slot name="display"/)
assert.match(inline, /<slot name="editor"/)
assert.match(inline, /pms-inline-field__surface/)
assert.match(form, /<label :for="fieldId"/)
assert.match(form, /<slot :described-by="describedBy" :invalid="Boolean\(error\)"/)
assert.match(form, /aria-describedby/)
assert.match(grid, /PMS_AG_GRID_FORM_CLASS\s*=\s*'pms-form-grid'/)
assert.match(grid, /pms-form-grid__cell/)
assert.match(entry, /export \{ default as PmsFormField \}/)
assert.match(entry, /export \{ default as PmsInlineField \}/)
assert.match(entry, /PMS_AG_GRID_FORM_CLASS/)
assert.match(tokens, /\.pms-inline-field__surface[\s\S]*height:\s*var\(--pms-form-control-height-compact\)/)
assert.match(tokens, /\.pms-form-grid \.ag-cell-inline-editing[\s\S]*box-shadow:/)
assert.match(tokens, /\.pms-form-grid \.ag-cell-inline-editing[\s\S]*\.el-input__wrapper/)

console.log('form system layout contract passed')
