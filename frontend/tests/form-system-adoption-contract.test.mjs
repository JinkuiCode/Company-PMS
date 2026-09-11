import assert from 'node:assert/strict'
import { readdirSync, readFileSync, statSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { resolve } from 'node:path'

const root = resolve(fileURLToPath(new URL('../src', import.meta.url)))
const allowed = `${resolve(root, 'form-system')}/`
const rawControls = /<el-(input|select|tree-select|date-picker|input-number|switch|checkbox|checkbox-group|segmented)(?:\s|>)/

function walk(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = resolve(dir, name)
    return statSync(path).isDirectory() ? walk(path) : [path]
  })
}

for (const path of walk(root).filter((path) => path.endsWith('.vue') && !path.startsWith(allowed))) {
  assert.doesNotMatch(readFileSync(path, 'utf8'), rawControls, `${path} must use @/form-system controls`)
}

console.log('form system adoption contract passed')
