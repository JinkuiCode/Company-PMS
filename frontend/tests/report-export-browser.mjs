import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
const browser = await chromium.launch({channel:'msedge',headless:true})
const page = await browser.newPage({viewport:{width:1366,height:768}})
await page.addInitScript(()=>localStorage.setItem('access_token','isolated-export-test'))
let jobs=[], submitted, canExport=true
await page.route('**/api/**', async route=>{
  const path=new URL(route.request().url()).pathname
  if(!path.startsWith('/api/'))return route.continue()
  if(path==='/api/auth/me')return route.fulfill({json:{id:987,username:'test',permissions:['report:inventory:view',...(canExport?['report:inventory:export']:[])]}})
  if(path==='/api/my-menus')return route.fulfill({json:[]})
  if(path.endsWith('/metadata'))return route.fulfill({json:{fields:['MaterialCode','MaterialName','FBaseQty'].map(key=>({key,label:key,width:140,value_type:key==='FBaseQty'?'number':'text',list_available:true})),organizations:[]}})
  if(path==='/api/reports/inventory')return route.fulfill({json:{items:[{FID:'hidden',MaterialCode:'001',MaterialName:'test',FBaseQty:1}],total:20001,queried_at:'2026-09-22'}})
  if(path==='/api/report-exports'){
    if(route.request().method()==='POST'){
      submitted=route.request().postDataJSON()
      jobs=[{id:'a'.repeat(32),report:'inventory',status:'running',processed:500,created_at:'2026-09-22T12:00:00',message:null}]
      return route.fulfill({status:202,json:jobs[0]})
    }
    return route.fulfill({json:jobs})
  }
  if(path.endsWith('/download'))return route.fulfill({body:Buffer.from('test-download'),contentType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'})
  throw Error(path)
})
try{
  await page.goto('http://127.0.0.1:5174/reports/inventory')
  await expect(page.getByRole('button',{name:'导出当前筛选'})).toBeEnabled()
  await page.getByRole('button',{name:'导出当前筛选'}).click()
  await expect(page.getByText('500 条主表数据')).toBeVisible()
  assert.deepEqual(submitted.columns,['MaterialCode','MaterialName','FBaseQty'])
  assert.equal(submitted.report,'inventory')
  await page.mouse.click(200,100)
  await expect(page.getByRole('button',{name:'导出任务 · 处理中'})).toBeEnabled()
  await page.getByRole('button',{name:'导出任务 · 处理中'}).click()
  await expect(page.getByText('500 条主表数据')).toBeVisible()
  await page.reload()
  await page.getByRole('button',{name:'导出任务 · 处理中'}).click()
  await expect(page.getByText('500 条主表数据')).toBeVisible()
  jobs=[{...jobs[0],status:'success',processed:20001,message:'导出完成，文件保留24小时'}]
  await page.getByRole('button',{name:'刷新导出任务'}).click()
  const downloaded=page.waitForEvent('download')
  await page.getByRole('button',{name:'下载',exact:true}).click()
  assert.ok((await downloaded).suggestedFilename().endsWith('.xlsx'))
  for(const width of [1366,1600]){
    await page.setViewportSize({width,height:900})
    await page.screenshot({path:`../.runtime/report-export-${width}.png`})
  }
  canExport=false
  await page.reload()
  await expect(page.getByRole('button',{name:'导出当前筛选'})).toHaveCount(0)
  console.log('report export browser: submit >10k, progress reopening, reload recovery, download and permission passed')
}finally{await browser.close()}
