import { test } from 'node:test'
import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
const path = new URL('../prototypes/theme-controls/theme.mjs', import.meta.url)

test('theme preview provides its isolated module', () => {
  assert.ok(existsSync(path), 'theme preview module has not been implemented')
})
test('approved palettes and fallback are preserved', async () => {
  assert.ok(existsSync(path), 'theme module missing')
  const { THEMES, normalizeTheme } = await import(path)
  assert.deepEqual(Object.keys(THEMES), ['blue', 'teal', 'graphite'])
  assert.deepEqual(Object.values(THEMES).map(t => t.brand), ['#2563eb', '#0f766e', '#27272a'])
  assert.equal(normalizeTheme('teal'), 'teal')
  assert.equal(normalizeTheme('invalid'), 'blue')
  assert.equal(normalizeTheme(null), 'blue')
})
test('preferences isolate users and handle invalid or unavailable storage', async () => {
  assert.ok(existsSync(path), 'theme module missing')
  const { createThemePreference } = await import(path)
  const values = new Map()
  const storage = { getItem: k => values.get(k) ?? null, setItem: (k,v) => values.set(k,v) }
  const a = createThemePreference(storage, 'preview', 'a')
  const b = createThemePreference(storage, 'preview', 'b')
  assert.equal(a.read(), 'blue')
  assert.equal(a.write('teal'), true)
  assert.equal(a.read(), 'teal')
  assert.equal(b.read(), 'blue')
  assert.equal(createThemePreference(storage, 'other', 'a').read(), 'blue')
  values.set(a.key, 'deleted-theme')
  assert.equal(a.read(), 'blue')
  const broken = createThemePreference({getItem(){throw Error('blocked')},setItem(){throw Error('blocked')}}, 'preview', 'a')
  assert.equal(broken.read(), 'blue')
  assert.equal(broken.write('graphite'), false)
})
