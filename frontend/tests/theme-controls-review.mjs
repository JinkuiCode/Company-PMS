import assert from 'node:assert/strict'
import { chromium, expect } from '@playwright/test'
import { writeFile } from 'node:fs/promises'
const browser = await chromium.launch({ channel: 'msedge', headless: true })
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } })
const page = await context.newPage()
page.setDefaultTimeout(4000)
const output = new URL('../../outputs/theme-controls/review-result.json', import.meta.url)
const results = []
const check = async (name, test) => {
  try { await test(); results.push({ name, passed: true }) }
  catch (error) { results.push({ name, passed: false, error: String(error) }) }
}
const select = name => page.locator('.pms-form-control').filter({ has: page.getByRole('combobox', { name, exact: true }) })
try {
  await check('incomplete and reversed date queries show errors and retain previous results', async () => {
    await page.goto('http://127.0.0.1:5184/')
    await page.locator('[data-field="code"]').getByRole('textbox').fill('DEMO-202601')
    await page.getByRole('button', { name: '查询', exact: true }).click()
    await expect(page.locator('.list-footer')).toContainText('共 1 条')
    const date = page.locator('[data-field="date"]')
    await date.getByRole('combobox', { name: '样稿值', exact: true }).fill('2026-10-10')
    await date.getByRole('combobox', { name: '样稿值', exact: true }).press('Tab')
    await page.locator('[data-field="code"]').getByRole('textbox').fill('')
    await page.getByRole('button', { name: '查询', exact: true }).click()
    await expect(date.getByRole('alert')).toContainText('请填写完整区间')
    await expect(page.locator('.list-footer')).toContainText('共 1 条')
    await date.getByRole('combobox', { name: '样稿结束值', exact: true }).fill('2026-10-01')
    await date.getByRole('combobox', { name: '样稿结束值', exact: true }).press('Tab')
    await page.getByRole('button', { name: '查询', exact: true }).click()
    await expect(date.getByRole('alert')).toContainText('开始日期不能晚于结束日期')
    await expect(page.locator('.list-footer')).toContainText('共 1 条')
  })
  await check('inline edit focuses immediately and Escape restores prior value', async () => {
    await page.goto('http://127.0.0.1:5184/')
    await page.getByRole('button', { name: '表单与状态', exact: true }).click()
    await page.locator('.inline-value').click()
    await expect(page.getByRole('textbox', { name: '行内备注', exact: true })).toBeFocused()
    await page.keyboard.type('draft')
    await page.keyboard.press('Escape')
    await expect(page.locator('.inline-value')).toContainText('可编辑备注')
    await expect(page.locator('.inline-value')).not.toContainText('draft')
  })
  await check('cross-tab theme sync survives reload of a themed URL', async () => {
    await page.goto('http://127.0.0.1:5184/')
    await page.getByRole('button', { name: '切换外观' }).click()
    await page.getByRole('menuitem', { name: '青绿' }).click()
    const sibling = await context.newPage()
    try {
      await sibling.goto('http://127.0.0.1:5184/')
      await sibling.getByRole('button', { name: '切换外观' }).click()
      await sibling.getByRole('menuitem', { name: '石墨' }).click()
      await expect(page.locator('html')).toHaveAttribute('data-preview-theme', 'graphite')
      await page.reload()
      await expect(page.locator('html')).toHaveAttribute('data-preview-theme', 'graphite')
    } finally { await sibling.close() }
  })
  await check('sorting applies before pagination', async () => {
    await page.goto('http://127.0.0.1:5184/')
    await select('每页条数').click()
    await page.getByRole('option', { name: '15 条/页', exact: true }).click()
    await page.getByRole('button', { name: '项目编码列筛选', exact: true }).click()
    await page.getByRole('dialog', { name: '项目编码列筛选面板', exact: true }).getByRole('button', { name: '降序', exact: true }).click()
    await expect(page.locator('.ag-center-cols-container .ag-row[row-index="0"] [col-id="code"]')).toHaveText('DEMO-202624')
    await page.locator('.el-pager').getByText('2', { exact: true }).click()
    await expect(page.locator('.ag-center-cols-container .ag-row[row-index="0"] [col-id="code"]')).toHaveCount(1)
    await expect(page.locator('.ag-center-cols-container .ag-row[row-index="0"] [col-id="code"]')).toHaveText('DEMO-202609')
  })
  await writeFile(output, JSON.stringify({ passed: results.every(r => r.passed), results }, null, 2))
  console.log(JSON.stringify(results, null, 2))
  assert.ok(results.every(r => r.passed), 'review regressions remain')
} finally { await browser.close() }
