import assert from 'node:assert/strict'
import { existsSync } from 'node:fs'
import { test } from 'node:test'
const file = new URL('../src/page-guide/navigation.ts', import.meta.url)
assert.ok(existsSync(file), '缺少独立说明页签的状态及路由模块')
const { guideDestinations, guideTabHref, readGuideView } = await import(file.href)
const { pageGuides } = await import('../src/page-guide/registry.ts')

test('guide link preserves only guide state in fragment, for each approved surface', () => {
  for (const key of Object.keys(pageGuides)) {
    const state = { section: 'fields', group: pageGuides[key].fields[0].group, search: '项目 & 数量', token: 'never', project_code: 'business' }
    const href = guideTabHref(key, state)
    const url = new URL(href, 'http://127.0.0.1:5174')
    assert.equal(url.pathname, `/page-guide/${key}`)
    assert.equal(url.search, '')
    assert.ok(!href.includes('never') && !href.includes('business'))
    // Search may hide this group, in which case it returns safely to all groups.
    assert.deepEqual(readGuideView(pageGuides[key], url.hash), { section: 'fields', group: '全部', search: state.search })
    const full = { section: 'fields', group: pageGuides[key].fields[0].group, search: '' }
    assert.deepEqual(readGuideView(pageGuides[key], new URL(guideTabHref(key, full), url.origin).hash), full)
  }
})
test('invalid states use safe defaults without crashing', () => {
  assert.deepEqual(readGuideView(pageGuides.purchase, '#section=evil&group=invalid'), { section: 'operations', group: '全部', search: '' })
  assert.doesNotThrow(() => readGuideView(pageGuides.stock, '#search=%E0%A4%A'))
})
test('standalone surfaces reuse existing page permission codes', () => {
  assert.deepEqual(Object.fromEntries(Object.entries(guideDestinations).map(([key, value]) => [key, value.permission])), {
    archive: 'project:archive:view', purchase: 'report:purchase:view', inventory: 'report:inventory:view', stock: 'report:stock-detail:list', feedback: 'feedback:view',
  })
})
