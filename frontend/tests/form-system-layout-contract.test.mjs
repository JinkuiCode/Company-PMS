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
assert.match(inline, /<slot name="label-suffix">/, 'Inline fields should allow source metadata without page-local label layouts')
assert.match(inline, /<slot name="actions" \/>/, 'Inline fields should allow compact field actions without page-local value containers')
assert.match(inline, /pms-inline-field__surface/)
assert.match(inline, /watch\([\s\S]*?props\.editing[\s\S]*?nextTick\(\)[\s\S]*?querySelector[\s\S]*?\.focus\(\)/, 'Inline editors should receive focus immediately after activation')
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
assert.match(tokens, /\.pms-form-grid \.ag-cell-inline-editing \.ag-cell-edit-wrapper/)
assert.match(
  tokens,
  /\.pms-standard-dialog-form \.el-form-item__content\s*\{[^}]*display:\s*block;[^}]*width:\s*100%;[^}]*\}/,
  'Standard dialog content should use a stable full-width block layout',
)

console.log('form system layout contract passed')
