import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(path, import.meta.url), 'utf8')
const entry = read('../src/form-system/index.ts')
const tokens = read('../src/form-system/form-tokens.css')
const shell = read('../src/form-system/components/PmsControlShell.vue')
const main = read('../src/main.ts')

assert.match(entry, /export \{ default as PmsControlShell \}/)
assert.match(entry, /export type \{[\s\S]*PmsControlSize[\s\S]*PmsOption/)
assert.match(tokens, /--pms-form-control-height-compact:\s*32px/)
assert.match(tokens, /--pms-form-control-height-regular:\s*36px/)
assert.match(tokens, /--pms-form-control-padding-x:\s*10px/)
assert.match(tokens, /--pms-form-control-line-height:\s*20px/)
assert.match(tokens, /\.pms-form-control[\s\S]*box-sizing:\s*border-box/)
assert.match(tokens, /\.pms-form-control--binary/)
assert.match(shell, /pms-form-control--\$\{props\.variant\}/)
assert.doesNotMatch(tokens, /^(?!\s*\.pms-form-control)[^\n]*\.el-(input|select|textarea)/m)
assert.match(main, /import '.\/form-system\/form-tokens\.css'/)

console.log('form system contract passed')
