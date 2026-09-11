import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const entry = read('../src/form-system/index.ts')
const tokens = read('../src/form-system/form-tokens.css')
const shell = read('../src/form-system/components/PmsControlShell.vue')
const main = read('../src/main.ts')
const listFilters = read('../src/components/PmsListFilters.vue')
const columnPicker = read('../src/components/PmsListColumnPicker.vue')

assert.match(entry, /export \{ default as PmsControlShell \}/)
assert.match(entry, /export type \{[\s\S]*PmsControlSize[\s\S]*PmsOption/)
assert.match(tokens, /--pms-form-control-height-compact:\s*32px/)
assert.match(tokens, /--pms-form-control-height-regular:\s*36px/)
assert.match(tokens, /--pms-form-control-padding-x:\s*10px/)
assert.match(tokens, /--pms-form-control-line-height:\s*20px/)
assert.match(tokens, /\.pms-form-control[\s\S]*box-sizing:\s*border-box/)
assert.match(tokens, /\.pms-form-control--binary/)
assert.match(shell, /pms-form-control--\$\{props\.variant\}/)
for (const line of tokens.split('\n').filter((line) => /\.el-(input|select|textarea)/.test(line))) {
  assert.match(
    line.trim(),
    /^\.pms-(form-control|form-grid)\b/,
    `Element Plus internals must stay under a form-system namespace: ${line}`,
  )
}
assert.match(main, /import '.\/form-system\/form-tokens\.css'/)
assert.match(listFilters, /from '@\/form-system'/, 'Shared list filters should consume the form-system public entry')
assert.match(columnPicker, /from '@\/form-system'/, 'Column picker should consume the form-system public entry')

for (const component of [
  'PmsTextControl',
  'PmsSelectControl',
  'PmsTreeSelectControl',
  'PmsDateControl',
  'PmsNumberControl',
  'PmsTextareaControl',
  'PmsSwitchControl',
  'PmsCheckboxControl',
  'PmsCheckboxGroupControl',
  'PmsSegmentedControl',
]) {
  assert.match(entry, new RegExp(`export \\{ default as ${component} \\}`))
  const source = read(`../src/form-system/components/${component}.vue`)
  assert.match(source, /defineOptions\(\{ inheritAttrs: false \}\)/)
  assert.match(source, /<PmsControlShell/)
  assert.match(source, /update:modelValue/)
}

const select = read('../src/form-system/components/PmsSelectControl.vue')
const checkboxGroup = read('../src/form-system/components/PmsCheckboxGroupControl.vue')
const segmented = read('../src/form-system/components/PmsSegmentedControl.vue')
assert.match(select, /options:\s*PmsOption\[\]/)
assert.match(select, /v-for="option in options"/)
assert.match(checkboxGroup, /options:\s*PmsOption\[\]/)
assert.match(segmented, /options:\s*PmsOption\[\]/)
assert.match(tokens, /\.pms-form-control \.el-input__wrapper[\s\S]*box-shadow:\s*none/)
assert.match(tokens, /\.pms-form-control \.el-select__input[\s\S]*margin-left:\s*0/)
assert.match(tokens, /\.pms-form-control :is\(input, textarea, button\):focus-visible[\s\S]*outline:\s*none/)

console.log('form system contract passed')
