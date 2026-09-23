import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
const path = new URL('../src/utils/detailSwitch.ts', import.meta.url)
const code = ts.transpileModule(readFileSync(path, 'utf8'), { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText
const { createDetailSwitch } = await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
let resolve, prompts = 0, applied = []
const gate = new Promise(r => { resolve = r })
const controller = createDetailSwitch(async () => { prompts++; return gate }, async row => applied.push(row))
const a = controller.select(1), b = controller.select(2)
resolve(true)
await Promise.all([a, b])
assert.equal(prompts, 1)
assert.deepEqual(applied, [2])
const canceled = createDetailSwitch(async () => false, async row => applied.push(row))
await canceled.select(3)
assert.deepEqual(applied, [2])
let finish
const pending = new Promise(r => { finish = r })
let result
const racing = createDetailSwitch(async () => true, async (row, current) => {
  if (row === 1) await pending
  if (current()) result = row
})
const slow = racing.select(1)
await Promise.resolve(); await Promise.resolve()
await racing.select(2); finish(); await slow
assert.equal(result, 2)
const close = racing.select(1); racing.invalidate(); await close
assert.equal(result, 2)
for (const file of ['ProjectArchive', 'ProjectList']) {
  const text = readFileSync(new URL(`../src/views/project/${file}.vue`, import.meta.url), 'utf8')
  assert.match(text, /@row-clicked=/)
  assert.match(text, /createDetailSwitch/)
}
console.log('detail switch latest-row, cancel and shared-guard tests passed')
