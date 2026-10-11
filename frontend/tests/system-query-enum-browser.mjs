import assert from 'node:assert/strict'
import { chromium } from '@playwright/test'
import { schemeStorageKey } from '../src/query-system/workspace.ts'

const base = process.env.PMS_TEST_URL || 'http://127.0.0.1:5174'
const definitions = [1,2].map(id=>({id,dict_code:`enum_${id}`,dict_name:id===1?'枚举A':'枚举B',mode:'configurable',allow_add:true,bindings:[],item_count:2}))
const rows = {1:[{id:11,item_value:'11',item_label:'Alpha',status:1},{id:12,item_value:'12',item_label:'Beta',status:0}],2:[{id:21,item_value:'21',item_label:'Gamma',status:1},{id:22,item_value:'22',item_label:'Delta',status:0}]}
const plans = Object.fromEntries(definitions.map(item=>[schemeStorageKey(901,`system-enum-values-${item.dict_code}`),JSON.stringify([{version:2,name:`${item.dict_name}个人方案`,isDefault:true,preferences:{},definitions:[{field:'item_label',shown:true,operator:'contains',value:null,valueEnd:null,schemaVersion:2}]}])]))
const browser = await chromium.launch({headless:true,channel:'chrome'})
const context = await browser.newContext({viewport:{width:1360,height:900}})
await context.addInitScript(plans=>{localStorage.setItem('access_token','isolated-enum-test');for(const [key,value] of Object.entries(plans))localStorage.setItem(key,value)},plans)
let holdA = false, releaseA
const writes = [], errors = []
await context.route(`${base}/api/**`,async route=>{
  const request = route.request(), path = new URL(request.url()).pathname.slice(4)
  if(request.method()!=='GET'){writes.push(path);await route.abort();return}
  let result = []
  if(path==='/auth/me')result={id:901,username:'enum-test',permissions:['system:enum:view'],role_codes:[],status:1}
  else if(path==='/dicts')result=definitions
  else if(path==='/dicts/1/items'){
    if(holdA)await new Promise(resolve=>{releaseA=resolve})
    result=rows[1]
  }else if(path==='/dicts/2/items')result=rows[2]
  await route.fulfill({status:200,contentType:'application/json',body:JSON.stringify(result)})
})
const page = await context.newPage()
page.on('pageerror',error=>errors.push(error.message))
const table = page.locator('.el-table__body-wrapper')
const query = page.locator('.pms-query-workspace')
const select = label=>page.locator('.enum-master-item').filter({hasText:label}).click()
try {
  await page.goto(base+'/system/enum')
  await table.getByText('Alpha',{exact:true}).waitFor()
  await query.getByText('枚举A个人方案 · 默认',{exact:true}).waitFor()
  await query.getByRole('textbox',{name:'查询1值',exact:true}).fill('Beta')
  await query.getByRole('button',{name:'查询',exact:true}).click()
  await table.getByText('Alpha',{exact:true}).waitFor({state:'hidden'})
  await page.locator('button[aria-label="状态列筛选"]:visible').click()
  const panel = page.getByRole('dialog',{name:'状态列筛选面板'})
  await panel.getByText('禁用',{exact:true}).waitFor()
  await panel.locator('.pms-column-filter-values label').last().click()
  await panel.getByRole('button',{name:'应用',exact:true}).click()
  await select('枚举B')
  await table.getByText('Gamma',{exact:true}).waitFor()
  await table.getByText('Delta',{exact:true}).waitFor()
  await query.getByText('枚举B个人方案 · 默认',{exact:true}).waitFor()
  assert.equal(await query.getByRole('textbox',{name:'查询1值',exact:true}).inputValue(),'')
  await page.locator('button[aria-label="显示名称列筛选"]:visible').click()
  const names = page.getByRole('dialog',{name:'显示名称列筛选面板'})
  await names.getByText('Gamma',{exact:true}).waitFor()
  assert.equal(await names.getByText('Beta',{exact:true}).count(),0)
  await names.getByRole('button',{name:'关闭',exact:true}).click()

  holdA=true
  const delayedRequest=page.waitForRequest(request=>new URL(request.url()).pathname==='/api/dicts/1/items')
  await select('枚举A')
  await delayedRequest
  await select('枚举B')
  await table.getByText('Gamma',{exact:true}).waitFor()
  const lateResponse=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/dicts/1/items')
  releaseA()
  await lateResponse
  await page.evaluate(()=>new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve))))
  assert.equal(await page.locator('.enum-title-line h2').innerText(),'枚举B')
  assert.equal(await table.getByText('Alpha',{exact:true}).count(),0)
  assert.equal(await table.getByText('Gamma',{exact:true}).count(),1)
  holdA=false
  await select('枚举A')
  await table.getByText('Alpha',{exact:true}).waitFor()
  await query.getByText('枚举A个人方案 · 默认',{exact:true}).waitFor()
  assert.deepEqual(await page.evaluate(keys=>Object.fromEntries(keys.map(key=>[key,localStorage.getItem(key)])),Object.keys(plans)),plans,'A/B个人方案原样保留')
  assert.deepEqual(errors,[])
  assert.deepEqual(writes,[])
  console.log('enum browser passed: late responses, isolated accepted query/columns/candidates, personal plans preserved')
}finally{releaseA?.();await browser.close()}
