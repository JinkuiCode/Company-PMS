import assert from 'node:assert/strict'
import { chromium, expect } from '@playwright/test'

const browser = await chromium.launch({ channel: 'msedge', headless: true })
try {
  for (const deviceScaleFactor of [1, 2]) {
    const context = await browser.newContext({ viewport: { width: 1366, height: 900 }, deviceScaleFactor })
    const page = await context.newPage()
    const errors = []
    page.on('pageerror', error => errors.push(error.message))
    await page.goto('http://127.0.0.1:5174/login')
    await expect(page.locator('.login-title')).toBeVisible()
    await expect(page.locator('.login-btn span')).toBeVisible()
    await page.evaluate(() => document.fonts.ready)
    const session = await context.newCDPSession(page)
    await session.send('DOM.enable')
    await session.send('CSS.enable')
    const { root } = await session.send('DOM.getDocument')
    for (const selector of ['.login-title', '.login-btn span']) {
      const { nodeId } = await session.send('DOM.querySelector', { nodeId: root.nodeId, selector })
      const { fonts } = await session.send('CSS.getPlatformFontsForNode', { nodeId })
      const renderedFonts = fonts.filter(font => font.glyphCount > 0)
      assert.ok(renderedFonts.length > 0, `${selector} should render text`)
      assert.ok(renderedFonts.every(font => font.isCustomFont && /NotoSansSC/.test(font.postScriptName)),
        `${selector} at DPR ${deviceScaleFactor} must render the bundled Chinese font: ${JSON.stringify(renderedFonts)}`)
      console.log(JSON.stringify({ selector, deviceScaleFactor, fonts: renderedFonts }))
    }
    assert.deepEqual(errors, [], 'Login should render without browser errors')
    await context.close()
  }
  console.log('PASS: application text and buttons render the bundled font at DPR 1 and 2')
} finally {
  await browser.close()
}
