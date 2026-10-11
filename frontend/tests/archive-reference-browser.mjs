import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
const browser=await chromium.launch({headless:true,channel:'msedge'})
const page=await browser.newPage({viewport:{width:1440,height:900}})
page.setDefaultTimeout(12000)
const requests=[],errors=[],failedRequests=[]
let fail=false
const rows=Array.from({length:125},(_,i)=>({id:i+1,project_code:`A-${String(i+1).padStart(4,'0')}`,project_name:i<2?'同名设备':`设备${i+1}`,product_line_id:i%2+1,is_enabled:i===1?0:1,archive_category:1,erp_sync_policy:'manual'}))
await page.addInitScript(()=>localStorage.setItem('access_token','isolated-reference-test'))
page.on('pageerror',e=>errors.push(e.message))
page.on('requestfailed',r=>failedRequests.push({url:r.url(),error:r.failure()}))
await page.route('**/api/**',async route=>{
 const u=new URL(route.request().url());if(!u.pathname.startsWith('/api/'))return route.continue();let body=[]
 if(u.pathname==='/api/auth/me')body={id:1,username:'reference-test',real_name:'引用试点验收',permissions:['project:archive:view']}
 else if(u.pathname==='/api/auth/product-categories')body={unrestricted:true}
 else if(u.pathname==='/api/product-lines/options')body={options:[{id:1,label:'8吋Bench'},{id:2,label:'Single'}],label_map:{1:'8吋Bench',2:'Single'}}
 else if(u.pathname.includes('/dicts/code/'))body=u.pathname.endsWith('/archive_category')?{items:[{value:'1',label:'主机'}],all_items:[{value:'1',label:'主机'}],label_map:{1:'主机'}}:{items:[],label_map:{}}
 else if(u.pathname==='/api/projects/archives/fields')body={items:[]}
 else if(u.pathname==='/api/projects/archives/list'){
  const params=Object.fromEntries(u.searchParams);requests.push(params)
  if(fail&&params.enabled==='all')return route.fulfill({status:503,json:{detail:'引用候选暂不可用'}})
  const filters=JSON.parse(params.filters||'[]')
  let found=rows.filter(r=>params.enabled==='all'||params.enabled==='false'?!r.is_enabled:r.is_enabled)
  if(params.enabled==='all')found=[...rows]
  if(params.keyword)found=found.filter(r=>`${r.project_code} ${r.project_name}`.includes(params.keyword))
  for(const c of filters)found=found.filter(r=>{
    if(c.operator==='reference')return c.value.includes(c.field.startsWith('project_')?r.id:r[c.field])
    if(c.operator==='in')return c.value.includes(r[c.field])
    if(c.operator==='contains')return String(c.field==='product_line_id'?(r.product_line_id===1?'8吋Bench':'Single'):r[c.field]).includes(c.value)
    return r[c.field]===c.value
  })
  const start=(Number(params.page)-1)*Number(params.page_size)
  body={total:found.length,items:found.slice(start,start+Number(params.page_size))}
 }
 await route.fulfill({json:body})
})
const panel=page.getByRole('dialog',{name:'统一筛选条件',exact:true})
const dialog=page.getByRole('dialog',{name:'引用项目档案',exact:true})
async function settle(){await page.waitForFunction(()=>!document.querySelector('[class*="-enter-active"],[class*="-leave-active"]'))}
async function pick(name,option){await settle();await page.getByRole('combobox',{name,exact:true}).locator('xpath=ancestor::div[contains(@class,"el-select__wrapper")][1]').click();await page.getByRole('option',{name:option,exact:true}).click()}
async function openReference(){await page.getByRole('button',{name:/添加筛选/}).click();if(!await panel.locator('.condition-row').count()){await panel.getByRole('button',{name:'增加条件',exact:true}).click();await pick('条件1字段','项目名称');await pick('条件1匹配方式','引用')}else await panel.getByRole('button',{name:'条件1引用值',exact:true}).click();await expect(dialog).toBeVisible();await expect(dialog.getByRole('status').filter({hasText:'正在加载'})).toHaveCount(0)}
try{
 await page.goto('http://127.0.0.1:5174/project/archive')
 await expect(page.getByText('共 124 条',{exact:true})).toBeVisible()
 await openReference()
 const before=requests.length
 await dialog.getByRole('textbox',{name:'搜索引用记录',exact:true}).fill('A-0001')
 assert.equal(requests.length,before,'输入不自动查询')
 await dialog.getByRole('button',{name:'查询',exact:true}).click()
 await expect(dialog.getByText('共 1 条',{exact:true})).toBeVisible()
 const checkbox=dialog.getByRole('checkbox',{name:'选择A-0001 同名设备',exact:true})
 await checkbox.locator('..').click()
 assert.equal(await checkbox.locator('xpath=ancestor::*[contains(@class,"pms-form-control--binary")][1]').evaluate(e=>getComputedStyle(e).outlineStyle),'none')
 await dialog.getByRole('button',{name:'批量粘贴',exact:true}).focus()
 await page.keyboard.press('Tab')
 assert.equal(await dialog.locator('.pms-form-control--binary').evaluateAll(els=>els.some(el=>el.querySelector(':focus-visible')&&getComputedStyle(el).outlineStyle!=='none')),true,'键盘焦点必须保留')
 await dialog.getByRole('textbox',{name:'搜索引用记录',exact:true}).fill('A-0002')
 await dialog.getByRole('textbox',{name:'搜索引用记录',exact:true}).press('Enter')
 await expect(dialog.getByText('共 1 条',{exact:true})).toBeVisible()
 await dialog.getByRole('checkbox',{name:'选择A-0002 同名设备',exact:true}).locator('..').click()
 await expect(dialog.getByText('已选明细（2 条）',{exact:true})).toBeVisible()
 await dialog.getByRole('button',{name:'重置',exact:true}).click()
 await expect(dialog.getByText('共 125 条',{exact:true})).toBeVisible()
 await dialog.getByRole('button',{name:'2',exact:true}).click()
 await expect(dialog.getByRole('checkbox',{name:'选择A-0051 设备51',exact:true}).locator('..')).toBeVisible()
 await expect(dialog.getByText('已选明细（2 条）',{exact:true})).toBeVisible()
 await dialog.getByRole('button',{name:'批量粘贴',exact:true}).click()
 await dialog.getByRole('textbox',{name:'批量查询数据',exact:true}).fill('A-0001\nA-0003\n不存在\nA-0001')
 await dialog.getByRole('button',{name:'批量查询',exact:true}).click()
 await expect(dialog.getByText('输入 3 项 · 匹配 2 条 · 未匹配 1 项',{exact:true})).toBeVisible()
 await expect(dialog.getByText('未匹配：不存在',{exact:true})).toBeVisible()
 await dialog.getByRole('checkbox',{name:'全选当前页',exact:true}).locator('..').click()
 await expect(dialog.getByText('已选明细（3 条）',{exact:true})).toBeVisible()
 await pick('批量匹配字段','名称')
 await dialog.getByRole('textbox',{name:'批量查询数据',exact:true}).fill('同名设备')
 await dialog.getByRole('button',{name:'批量查询',exact:true}).click()
 await expect(dialog.getByText('多条匹配，请核对勾选：同名设备（2条）',{exact:true})).toBeVisible()
 await dialog.getByRole('textbox',{name:'批量查询数据',exact:true}).fill('A\tB')
 await dialog.getByRole('button',{name:'批量查询',exact:true}).click()
 await expect(dialog.getByText('请只复制一列数据，不支持多列粘贴',{exact:true})).toBeVisible()
 await expect(dialog.getByText('共 2 条',{exact:true})).toBeVisible()
 await pick('批量匹配字段','编码')
 await dialog.getByRole('textbox',{name:'批量查询数据',exact:true}).fill('A-0001\nA-0003\n不存在\nA-0001')
 await dialog.getByRole('button',{name:'批量查询',exact:true}).click()
 await expect(dialog.getByText('输入 3 项 · 匹配 2 条 · 未匹配 1 项',{exact:true})).toBeVisible()
 await expect(dialog.getByText('已选明细（3 条）',{exact:true})).toBeVisible()
 for(const width of [1182,390]){
  await page.setViewportSize({width,height:820});await settle()
  const b=await dialog.evaluate(e=>{const r=e.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:innerWidth,height:innerHeight}})
  assert.ok(b.left>=-1&&b.right<=b.width+1&&b.top>=-1&&b.bottom<=b.height+1,JSON.stringify(b))
 }
 await page.setViewportSize({width:1440,height:900});await settle()
 await page.screenshot({path:'../.runtime/archive-reference-pilot.png',fullPage:true})
 await dialog.getByRole('button',{name:'确认引用',exact:true}).click()
 await expect(panel).toBeVisible()
 await expect(panel.getByRole('button',{name:'条件1引用值',exact:true})).toContainText('已选 3 条')
 await panel.getByRole('button',{name:'应用条件',exact:true}).click()
 await expect(page.getByText('共 2 条',{exact:true})).toBeVisible()
 assert.deepEqual(JSON.parse(requests.at(-1).filters)[0].value,[1,2,3],'按稳定档案ID，不保存名称')
 await openReference()
 await dialog.getByRole('button',{name:'移除A-0001 同名设备',exact:true}).click()
 await dialog.getByRole('button',{name:'取消',exact:true}).click()
 await expect(panel.getByRole('button',{name:'条件1引用值',exact:true})).toContainText('已选 3 条')
 await panel.getByRole('button',{name:'取消',exact:true}).click()
 await page.getByRole('button',{name:'保存查询方案',exact:true}).click()
 await page.getByRole('textbox',{name:'方案名称',exact:true}).fill('引用档案试点')
 await page.getByRole('button',{name:'保存',exact:true}).click()
 await page.getByRole('button',{name:'清空筛选',exact:true}).click()
 await expect(page.getByText('共 124 条',{exact:true})).toBeVisible()
 await pick('查询方案','引用档案试点')
 await page.getByRole('button',{name:'查询',exact:true}).click()
 await expect(page.getByText('共 2 条',{exact:true})).toBeVisible()
 fail=true
 await openReference()
 await expect(dialog.getByRole('alert')).toBeVisible()
 await expect(dialog.getByRole('button',{name:'确认引用',exact:true})).toBeDisabled()
 fail=false
 await dialog.getByRole('button',{name:'查询',exact:true}).click()
 await expect(dialog.getByText('共 125 条',{exact:true})).toBeVisible()
 await dialog.getByRole('button',{name:'取消',exact:true}).click()
 await panel.getByRole('button',{name:'增加条件',exact:true}).click()
 await pick('条件2字段','产品线');await pick('条件2匹配方式','等于');await pick('条件2值','Single')
 await panel.getByRole('button',{name:'应用条件',exact:true}).click()
 await expect(panel.getByText('部分引用记录不在当前产品线或权限范围，请重新选择',{exact:true})).toBeVisible()
 assert.deepEqual(errors,[])
 console.log('archive reference browser passed: explicit queries, paged accumulation, batch reports, cancel/restore, identity, failure closed, line revalidation, checkbox and responsive bounds')
}catch(e){await page.screenshot({path:'../.runtime/archive-reference-failure.png',fullPage:true});console.error({url:page.url(),errors,failedRequests,requests:requests.slice(-5)});throw e}
finally{await browser.close()}
