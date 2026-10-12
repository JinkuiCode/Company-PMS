import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { test } from 'node:test'
const row = readFileSync(new URL('../src/query-system/PmsQueryConditionRow.vue', import.meta.url), 'utf8')
const workspace = readFileSync(new URL('../src/query-system/PmsQueryWorkspace.vue', import.meta.url), 'utf8')
test('approved compact width is stable rather than growing across available space', () => {
  assert.match(row, /grid-template-columns:96px 68px minmax\(0,1fr\) 18px/)
  assert.match(workspace, /flex:0 0 326px/)
  assert.match(workspace, /flex-basis:434px/)
  assert.match(row, /\.is-regular\{grid-template-columns:108px 80px minmax\(108px,1fr\) 20px/)
  assert.match(row, /\.pms-condition-reference>span\{[^}]*text-overflow:ellipsis/)
  assert.match(row, /\.pms-condition-reference>small\{flex-shrink:0/)
})
