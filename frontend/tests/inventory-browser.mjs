import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
const browser = await chromium.launch({channel: 'msedge', headless: true})
const page = await browser.newPage({viewport: {width: 1366, height: 768}})
await page.addInitScript(() => localStorage.setItem('access_token', 'inventory-test'))
const keys = ['FID','Organization','Stock','MaterialCode','MaterialName','FSPECIFICATION','Brand','Material','SupplierNumber','FBaseQty','Unit']
const labels = ['库存内码','组织','仓库','物料编码','物料名称','规格型号','品牌','材质','供应商编码','基本单位数量','单位']
let fail = false, releaseOld, last
const errors = []
page.on('pageerror', e => errors.push(e.message))
await page.route('**/api/**', async route => {
  const url = new URL(route.request().url()), path = url.pathname
  if (!path.startsWith('/api/')) return route.continue()
  if(path === '/api/auth/me') return route.fulfill({json:{id:999, username:'test', real_name:'验收用户', permissions:['report:inventory:view','report:inventory:export'],role_codes:[],product_line_ids:[1]}})
  if(path === '/api/my-menus') return route.fulfill({json:[{id:1,menu_name:'报表中心',menu_type:'M',icon:'Document',children:[{id:2,menu_name:'即时库存查询',path:'/reports/inventory',icon:'Document'}]}]})
  if(path === '/api/report-exports') return route.fulfill({json:[]})
  if(path.endsWith('/metadata')) return route.fulfill({json:{fields:keys.map((key,i)=>({key,label:labels[i],value_type:key==='FBaseQty'?'number':'text',width:i===4?220:140,description:labels[i],list_available:true})).filter(f=>f.key!=='FID'),organizations:[{value:100,label:'8吋半导体'}]}})
  if(path.endsWith('/options')) return route.fulfill({json:{items:[{value:'原料仓',label:'原料仓'}]}})
  if(path === '/api/reports/inventory') {
    last = Object.fromEntries(url.searchParams)
    const keyword = last.keyword, start = (Number(last.page)-1)*Number(last.page_size)
    if(keyword === '旧') await new Promise(resolve => {releaseOld=resolve})
    if(fail) return route.fulfill({status:503,json:{detail:'测试来源暂时不可用'}})
    return route.fulfill({json:{total:126,queried_at:'2026-09-22T09:00:00Z',items:Array.from({length:Math.min(Number(last.page_size),126-start)},(_,i)=>Object.fromEntries(keys.map((key,j)=>[key,key==='FID'?String(start+i+1):key==='FBaseQty'?'-12.50':key==='MaterialName'?(keyword||'阀门及较长物料名称用于检查截断'):key==='MaterialCode'?`MAT-${start+i+1}`:['','8吋半导体','原料仓','','','DN25','品牌','不锈钢','SUP-001','','个'][j]])))}})
  }
  throw Error(`Unexpected request ${path}`)
})
try {
  await page.goto('http://127.0.0.1:5174/reports/inventory')
  await expect(page.locator('.pagination-total')).toHaveText('共 126 条')
  assert.equal(last.page_size,'50')
  await page.getByRole('button',{name:'2',exact:true}).click()
  await expect.poll(()=>last.page).toBe('2')
  await expect(page.locator('.ag-row[row-index="0"] .ag-cell[col-id="MaterialCode"]')).toHaveText('MAT-51')
  await expect(page.locator('.ag-cell[col-id="FID"]')).toHaveCount(0)
  const search = page.getByRole('textbox',{name:'搜索库存物料'})
  await search.fill('新物料')
  await expect.poll(()=>last.keyword).toBe('新物料')
  assert.equal(last.page,'1')
  await expect(page.locator('.ag-cell[col-id="MaterialName"]').first()).toHaveText('新物料')
  await search.fill('旧')
  await expect.poll(()=>!!releaseOld).toBe(true)
  await search.fill('新')
  await expect(page.locator('.ag-cell[col-id="MaterialName"]').first()).toHaveText('新')
  releaseOld()
  await page.getByRole('button',{name:'刷新',exact:true}).click()
  await expect(page.locator('.ag-cell[col-id="MaterialName"]').first()).toHaveText('新')
  fail=true
  await page.getByRole('button',{name:'刷新',exact:true}).click()
  await expect(page.getByRole('alert').filter({hasText:'库存数据加载失败'})).toBeVisible()
  await expect(page.locator('.ag-cell[col-id="FID"]')).toHaveCount(0)
  fail=false
  await page.getByRole('button',{name:'重试',exact:true}).click()
  await expect(page.locator('.pagination-total')).toHaveText('共 126 条')
  await page.locator('.page-size-select').selectOption('20')
  await expect.poll(()=>last.page_size).toBe('20')
  assert.equal(last.page,'1')
  await page.getByRole('button',{name:'打开即时库存列设置'}).click()
  await expect(page.locator('.column-picker-panel')).toBeVisible()
  await page.locator('.column-picker-panel').getByRole('button',{name:'保存',exact:true}).click()
  await expect(page.locator('.column-picker-panel')).not.toBeVisible()
  await expect(page.locator('.el-message')).toHaveCount(0, {timeout: 10000})
  await page.mouse.move(10,10)
  assert.ok(await page.evaluate(()=>JSON.parse(localStorage.getItem('pms:inventory-report:v1:999')).columns.length===10))
  for(const width of [1366,1600]) {
    await page.setViewportSize({width,height:900})
    await page.evaluate(()=>document.fonts.ready)
    await page.screenshot({path:`../.runtime/inventory-formal-${width}.png`})
    const footer=await page.locator('.custom-pagination').boundingBox()
    assert.ok(footer.y+footer.height<=900)
  }
  assert.deepEqual(errors,[])
  console.log('inventory browser checks passed')
} finally { await browser.close() }
