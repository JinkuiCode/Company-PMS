import { chromium, expect } from '@playwright/test'

const browser = await chromium.launch({ channel: 'msedge', headless: true })
try {
  const page = await browser.newPage({ viewport: { width: 1600, height: 1000 } })
  await page.goto('http://127.0.0.1:5174/prototypes/report-query-v2.html')
  for (const report of ['即时库存查询', '采购进度查询', '物料收发明细']) {
    await page.getByRole('button', { name: report, exact: true }).click()
    await page.getByRole('button', { name: '添加条件', exact: true }).click()
    const panel = page.locator('.pms-report-conditions')
    await panel.getByRole('button', { name: '添加条件', exact: true }).click()
    await page.locator('.pms-form-control').filter({has:page.getByRole('combobox', { name: '条件1字段', exact: true })}).click()
    const option = page.getByRole('option', { name: '备注', exact: true })
    await option.click()
    await expect(panel).toBeVisible()
    await page.locator('.pms-form-control').filter({has:page.getByRole('combobox', { name: '条件1运算符', exact: true })}).click()
    await page.getByRole('option', { name: '结尾是', exact: true }).click()
    await expect(panel).toBeVisible()
    await page.getByRole('textbox', { name: '条件1值', exact: true }).fill('回归验证')
    await page.getByRole('button', { name: '应用条件', exact: true }).click()
    await expect(page.locator('.preview-applied')).toContainText('回归验证')
    await page.getByRole('button', { name: '添加条件 (1)', exact: true }).click()
    await page.locator('.pms-form-control').filter({has:page.getByRole('combobox', { name: '条件1字段', exact: true })}).click()
    await page.getByRole('option', { name: '单据状态', exact: true }).or(page.getByRole('option', { name: '库存状态', exact: true })).click()
    await page.locator('.pms-form-control').filter({has:page.getByRole('combobox', { name: '条件1值', exact: true })}).click()
    await page.getByRole('option', { name: report === '即时库存查询' ? '冻结' : '审核中', exact: true }).click()
    await expect(panel).toBeVisible()
    if (report !== '即时库存查询') {
      await page.locator('.pms-form-control').filter({has:page.getByRole('combobox', { name: '条件1字段', exact: true })}).click()
      await page.getByRole('option', { name: report === '采购进度查询' ? '申请日期' : '日期', exact: true }).click()
      await page.locator('.pms-form-control').filter({has:page.getByRole('combobox', { name: '条件1值', exact: true })}).click()
      await panel.locator('.el-date-table:visible td.available:not(.prev-month):not(.next-month)').last().click()
      await expect(panel).toBeVisible()
    }
    await panel.getByRole('button', { name: '取消', exact: true }).click()
    await expect(panel).toBeHidden()
    await expect(page.locator('.preview-applied')).toContainText('回归验证')
  }
  console.log('PASS: nested field/operator/enum/calendar selection preserves report filter draft')
} finally { await browser.close() }
