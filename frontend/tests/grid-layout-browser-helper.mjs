import { expect } from '@playwright/test'
import assert from 'node:assert/strict'

export async function verifyColumnLayout(page, id, label) {
  await verifyDividers(page)
  const codeHeader = page.locator('.ag-header-cell[col-id="project_code"]')
  const oldWidth = (await codeHeader.boundingBox()).width
  const resize = await codeHeader.locator('.ag-header-cell-resize').boundingBox()
  await page.mouse.move(resize.x + 1, resize.y + resize.height / 2)
  await page.mouse.down()
  await page.mouse.move(resize.x + 25, resize.y + resize.height / 2, { steps: 6 })
  await page.mouse.up()
  await expect.poll(async () => (await codeHeader.boundingBox()).width).toBe(oldWidth + 24)
  await page.getByRole('button', { name: /打开.*列设置/ }).click()
  await expect(page.getByRole('button', { name: '保存', exact: true })).toBeVisible()
  const field = page.locator(`.layout-field[data-column="${id}"]`)
  await field.locator('.el-select__wrapper').click()
  await page.getByRole('option', { name: '右侧冻结', exact: true }).click()
  const input = field.getByRole('spinbutton')
  await input.fill('180')
  await input.press('Tab')
  await page.screenshot({ path: `/tmp/pms-unified-editing-${id}.png` })
  await expect(page.locator(`.ag-pinned-right-header [col-id="${id}"]`)).toHaveCount(0)
  await page.getByRole('button', { name: '保存', exact: true }).click()
  const header = page.locator(`.ag-pinned-right-header [col-id="${id}"]`)
  await expect(header).toBeVisible()
  await expect.poll(async () => Math.round((await header.boundingBox()).width)).toBe(180)
  const divider = await page.locator('.ag-pinned-right-header').evaluate(el => getComputedStyle(el).borderLeftWidth)
  assert.equal(divider, '1px')
  await page.screenshot({ path: `/tmp/pms-column-layout-${id}.png` })
  await page.reload()
  await expect(header).toBeVisible()
  await expect.poll(async () => Math.round((await header.boundingBox()).width)).toBe(180)
  await page.getByRole('button', { name: /打开.*列设置/ }).click()
  await field.locator('.el-select__wrapper').click()
  await page.getByRole('option', { name: '中间滚动', exact: true }).click()
  const up = page.getByRole('button', { name: `上移${label}`, exact: true })
  await expect(up).toBeEnabled()
  await up.click()
  await page.getByRole('button', { name: '保存', exact: true }).click()
  const order = await page.locator('.ag-header-viewport .ag-header-cell').evaluateAll(els => els.map(el => el.getAttribute('col-id')))
  await page.reload()
  await expect(page.locator('.ag-header-viewport .ag-header-cell').first()).toBeVisible()
  await expect.poll(async () => page.locator('.ag-header-viewport .ag-header-cell').evaluateAll(els => els.map(el => el.getAttribute('col-id')))).toEqual(order)
  await page.getByRole('button', { name: /打开.*列设置/ }).click()
  const transfer = await page.evaluateHandle(() => new DataTransfer())
  await field.dispatchEvent('dragstart', { dataTransfer: transfer })
  await page.locator('.layout-zone').first().dispatchEvent('drop', { dataTransfer: transfer })
  await field.dispatchEvent('dragend')
  await page.getByRole('button', { name: '取消', exact: true }).click()
  await expect(page.locator(`.ag-pinned-left-header [col-id="${id}"]`)).toHaveCount(0)
  await page.getByRole('button', { name: /打开.*列设置/ }).click()
  await page.getByRole('button', { name: '恢复默认', exact: true }).click()
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.locator(`.ag-pinned-right-header [col-id="${id}"]`)).toHaveCount(0)
  await page.locator('.ag-body-horizontal-scroll-viewport').evaluate(el => { el.scrollLeft = 0 })
  await page.screenshot({ path: `/tmp/pms-unified-before-hide-${id}.png` })
  await expect(page.locator(`.ag-header-cell[col-id="${id}"]`)).toBeVisible()
  await page.getByRole('button', { name: /打开.*列设置/ }).click()
  await page.locator(`.layout-field[data-column="${id}"] .el-checkbox`).click()
  await expect(page.locator(`.ag-header-cell[col-id="${id}"]`)).toBeVisible()
  await page.getByRole('button', { name: '取消', exact: true }).click()
  await expect(page.locator(`.ag-header-cell[col-id="${id}"]`)).toBeVisible()
  await page.getByRole('button', { name: /打开.*列设置/ }).click()
  await page.locator(`.layout-field[data-column="${id}"] .el-checkbox`).click()
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await page.reload()
  await expect(page.locator(`.ag-header-cell[col-id="${id}"]`)).toHaveCount(0)
  await page.getByRole('button', { name: /打开.*列设置/ }).click()
  await page.getByPlaceholder('搜索字段', { exact: true }).fill(label)
  await page.locator('.hidden-field .el-checkbox').filter({ hasText: label }).click()
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(page.locator(`.ag-header-cell[col-id="${id}"]`)).toBeVisible()
  await verifyDividers(page)
}

export async function verifyDynamicColumnDraft(page) {
  const header = page.locator('.ag-pinned-right-header [col-id="sheet:configuration"]')
  await expect(page.locator('.column-picker-panel')).toBeHidden()
  await page.getByRole('button', { name: /打开.*列设置/ }).click()
  await page.getByPlaceholder('搜索字段', { exact: true }).fill('配置说明')
  await expect(page.getByPlaceholder('搜索字段', { exact: true })).toHaveValue('配置说明')
  await expect(page.locator('.hidden-fields')).toHaveAttribute('open', '')
  await page.locator('.hidden-field .el-checkbox').filter({ hasText: '配置说明' }).click()
  const field = page.locator('.layout-field[data-column="sheet:configuration"]')
  await field.locator('.el-select__wrapper').click()
  await page.getByRole('option', { name: '右侧冻结', exact: true }).click()
  await field.getByRole('spinbutton').fill('260')
  await expect(header).toHaveCount(0)
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(header).toBeVisible()
  await expect.poll(async () => Math.round((await header.boundingBox()).width)).toBe(260)
  await page.reload()
  await expect(header).toBeVisible()
  await expect.poll(async () => Math.round((await header.boundingBox()).width)).toBe(260)
  await page.getByRole('button', { name: /打开.*列设置/ }).click()
  await page.getByRole('button', { name: '恢复默认', exact: true }).click()
  await expect(header).toBeVisible()
  await page.getByRole('button', { name: '保存', exact: true }).click()
  await expect(header).toHaveCount(0)
}

async function verifyDividers(page) {
  const edges = await page.locator('.pms-ag-grid').evaluate(grid => {
    const edge = (selector, side) => {
      const style = getComputedStyle(grid.querySelector(selector))
      return [style[`border${side}Width`], style[`border${side}Color`]]
    }
    return {
      leftHeader: edge('.ag-pinned-left-header', 'Right'),
      rightHeader: edge('.ag-pinned-right-header', 'Left'),
      leftCell: edge('.ag-cell-last-left-pinned', 'Right'),
      rightCell: edge('.ag-cell-first-right-pinned', 'Left'),
      leftContainer: edge('.ag-pinned-left-cols-container', 'Right')[0],
      rightContainer: edge('.ag-pinned-right-cols-container', 'Left')[0],
    }
  })
  assert.equal(edges.leftContainer, '0px', 'body container must not duplicate cell divider')
  assert.equal(edges.rightContainer, '0px', 'body container must not duplicate cell divider')
  assert.equal(edges.leftHeader[0], '1px')
  for (const key of ['rightHeader', 'leftCell', 'rightCell']) assert.deepEqual(edges[key], edges.leftHeader, key)
}
