import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'

const browser = await chromium.launch({ headless: true, channel: 'msedge' })
try {
  const page = await browser.newPage({ viewport: { width: 1366, height: 768 } })
  await page.goto('http://127.0.0.1:5174/login')
  await page.evaluate(async () => {
    const { createApp, h } = await import('/node_modules/.vite/deps/vue.js')
    const { default: ElementPlus } = await import('/node_modules/.vite/deps/element-plus.js')
    const { PmsNumberControl } = await import('/src/form-system/index.ts')
    const host = document.createElement('div')
    host.id = 'number-matrix'
    host.style.cssText = 'position:fixed;inset:0;z-index:9999;background:white;padding:24px;display:grid;grid-template-columns:repeat(3,220px);gap:16px;align-content:start'
    document.body.append(host)
    const variants = [
      {}, { controls: false }, { controlsPosition: 'right' }, { disabled: true }, { readonly: true },
    ]
    createApp({ render: () => ['compact', 'regular'].flatMap(size => variants.map((props, i) =>
      h('div', { 'data-case': `${size}-${i}` }, [h('p', `${size}-${i}`), h(PmsNumberControl, { modelValue: 999, size, ...props })]))) }).use(ElementPlus).mount(host)
  })
  await expect(page.locator('#number-matrix input')).toHaveCount(10)
  const geometry = await page.locator('#number-matrix [data-case]').evaluateAll(els => els.map(el => {
    const input = el.querySelector('input').getBoundingClientRect()
    const buttons = [...el.querySelectorAll('.el-input-number__decrease,.el-input-number__increase')].map(b => b.getBoundingClientRect())
    return { name: el.dataset.case, width: input.width, overlap: buttons.some(b => input.left < b.right && input.right > b.left) }
  }))
  for (const item of geometry) assert.ok(!item.overlap && item.width > 40, JSON.stringify(item))
  for (const size of ['compact', 'regular']) {
    for (const index of [3, 4]) await expect(page.locator(`[data-case="${size}-${index}"] input`)).toBeDisabled()
  }
  await page.screenshot({ path: '/tmp/pms-number-controls.png' })
  console.log('number-control browser passed: compact/regular, buttons/no-buttons/right-buttons/disabled/readonly')
} finally { await browser.close() }
