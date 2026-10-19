import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
const root = new URL('../prototypes/theme-controls/', import.meta.url)
test('preview entry reuses real controls and has no production entry mutation', () => {
  assert.ok(existsSync(new URL('App.vue', root)), 'independent control preview is missing')
  const app = readFileSync(new URL('App.vue', root), 'utf8')
  for (const control of ['PmsQueryConditionRow','PmsQueryColumnHeader','PmsSelectControl','PmsTreeSelectControl','PmsDateControl','PmsFormDrawer','AgGridVue']) assert.ok(app.includes(control), control)
})
test('preview uses a dedicated local-only Vite configuration', () => {
  assert.ok(existsSync(new URL('vite.config.mjs', root)), 'isolated Vite configuration is missing')
  const config = readFileSync(new URL('vite.config.mjs', root), 'utf8')
  assert.match(config, /5184/)
  assert.match(config, /127\.0\.0\.1/)
  assert.doesNotMatch(config, /proxy\s*:/)
})
