import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
const browser = await chromium.launch({headless:true,channel:'msedge'})
const page = await browser.newPage({viewport:{width:1440,height:900}})
page.setDefaultTimeout(10000)
const requests=[], errors=[]
page.on('pageerror',e=>errors.push(e.message))
await page.addInitScript(()=>{
 localStorage.setItem('access_token','isolated-query-test')
 const base={keyword:'',enabled:'true',categories:[1],productCategory:null,pageSize:20,columns:{selected_column_keys:['customer'],columnState:[{colId:'project_name',width:245}]}}
 localStorage.setItem('pms:archive:query-plans:1',JSON.stringify([
  {version:1,name:'旧方案兼容',state:{...base,conditions:[{id:3,field:'project_name',operator:'contains',value:'Pump',valueEnd:''}]}},
  {version:1,name:'失效字段方案',state:{...base,conditions:[{id:4,field:'password',operator:'equals',value:'x',valueEnd:'',schemaVersion:2}]}}
 ]))
})
const rows=Array.from({length:125},(_,i)=>({id:i+1,project_code:`Q-${String(125-i).padStart(4,'0')}`,project_name:i%3===0?'Pump%_':i%3===1?'Pump':'Valve',
  business_product_line_id:i%2+1,product_line_id:i%2+1,product_line_name:i%2?'Single':'8吋Bench',manager_name:i===0?'历史负责人':'现任负责人',archive_category:1,is_enabled:1,quantity:i%3*10,can_delete:false,erp_sync_policy:'manual'}))
await page.route('**/api/**',async route=>{
 const u=new URL(route.request().url()); if(!u.pathname.startsWith('/api/')) return route.continue(); let body=[]
 if(u.pathname==='/api/auth/me') body={id:1,username:'test',real_name:'试点验收',permissions:['project:archive:view']}
 else if(u.pathname==='/api/auth/product-categories')body={unrestricted:true}
 else if(u.pathname==='/api/product-lines/options')body={options:[{id:1,label:'8吋Bench'},{id:2,label:'Single'}],label_map:{1:'8吋Bench',2:'Single'}}
 else if(u.pathname.includes('/dicts/code/'))body=u.pathname.endsWith('/archive_category')?{items:[{value:'1',label:'主机'},{value:'2',label:'辅机'}],all_items:[{value:'1',label:'主机'},{value:'2',label:'辅机'}],label_map:{1:'主机',2:'辅机'}}:{items:[],label_map:{}}
 else if(u.pathname==='/api/projects/archives/fields')body={items:[]}
 else if(u.pathname==='/api/projects/archives/list'){
  const p=Object.fromEntries(u.searchParams);requests.push(p);let chosen=rows.filter(r=>p.enabled!=='false')
  if(p.keyword)chosen=chosen.filter(r=>r.project_code.includes(p.keyword)||r.project_name.includes(p.keyword))
  for(const c of JSON.parse(p.filters||'[]')){
   chosen=chosen.filter(r=>{
    const v=r[c.field]
    if(c.operator==='in')return c.value.includes(v)
    if(c.operator==='notIn')return v!=null&&!c.value.includes(v)
    if(c.operator==='notEquals')return c.schemaVersion===2?v!=null&&v!==c.value:v!==c.value
    if(c.operator==='isEmpty')return v==null||v===''
    if(c.operator==='notEmpty')return v!=null&&v!==''
    if(c.operator==='notContains')return v!=null&&!String(v).includes(c.value)
    if(c.operator==='contains')return v!=null&&String(v).includes(c.value)
    if(c.operator==='startsWith')return String(v).startsWith(c.value)
    if(c.operator==='between')return v>=c.value&&v<=c.valueEnd
    return v===c.value
   })
  }
  const start=(Number(p.page)-1)*Number(p.page_size);body={total:chosen.length,items:chosen.slice(start,start+Number(p.page_size))}
 }
 await route.fulfill({json:body})
})
const panel=page.getByRole('dialog',{name:'统一筛选条件',exact:true})
async function settle(){await page.waitForFunction(()=>!document.querySelector('[class*="-enter-active"],[class*="-leave-active"]'))}
async function pick(name, option){await settle();await page.getByRole('combobox',{name,exact:true}).locator('xpath=ancestor::div[contains(@class,"el-select__wrapper")][1]').click();await page.getByRole('option',{name:option,exact:true}).click()}
try{
 await page.goto('http://127.0.0.1:5174/project/archive')
 await expect(page.getByText('共 125 条',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:'2',exact:true}).click()
 await expect.poll(()=>requests.at(-1).page).toBe('2')
 await page.getByRole('button',{name:/添加筛选/}).click()
 await expect(panel).toBeVisible()
 await expect(panel).toBeFocused()
 await panel.getByRole('button',{name:'增加条件',exact:true}).click()
 await pick('条件1字段','产品线')
 await pick('条件1匹配方式','属于')
 await pick('条件1值','8吋Bench')
 await page.getByRole('option',{name:'Single',exact:true}).click()
 await panel.locator('header').click()
 for(const width of [1920,1182,390]) {
  await page.setViewportSize({width,height:900});await settle()
  await expect.poll(()=>panel.evaluate(e=>{const r=e.getBoundingClientRect();return r.right<=innerWidth+1&&r.left>=-1})).toBe(true)
  const bounds=await panel.locator('.condition-value .el-select__wrapper').evaluate(e=>{
   const r=e.getBoundingClientRect();return [...e.querySelectorAll('.el-tag')].map(t=>{const b=t.getBoundingClientRect();return {left:b.left-r.left,right:r.right-b.right,top:b.top-r.top,bottom:r.bottom-b.bottom}})
  })
  assert.ok(bounds.length,'多选标签存在');assert.ok(bounds.every(b=>Object.values(b).every(v=>v>=-0.5)),JSON.stringify({width,bounds}))
 }
 await page.setViewportSize({width:1440,height:900});await settle()
 await page.screenshot({path:'../.runtime/unified-archive-query-multiselect.png',fullPage:true})
 const count=requests.length
 await panel.getByRole('button',{name:'取消',exact:true}).click()
 await expect(page.getByRole('button',{name:/添加筛选/})).toBeFocused()
 await settle();assert.equal(requests.length,count,'取消草稿不查询')
 await page.getByRole('button',{name:/添加筛选/}).click()
 assert.equal(await panel.locator('.condition-row').count(),0)
 await panel.getByRole('button',{name:'增加条件',exact:true}).click()
 await pick('条件1字段','产品线');await pick('条件1匹配方式','属于');await pick('条件1值','8吋Bench')
 await panel.getByRole('button',{name:'应用条件',exact:true}).click()
 await expect(page.getByText('共 63 条',{exact:true})).toBeVisible()
 assert.equal(requests.at(-1).page,'1')
 assert.equal(JSON.parse(requests.at(-1).filters)[0].schemaVersion,2)
 await page.getByRole('button',{name:'2',exact:true}).click()
 await expect.poll(()=>requests.at(-1).page).toBe('2')
 assert.deepEqual(JSON.parse(requests.at(-1).filters)[0].value,[1])
 await page.getByRole('button',{name:'保存查询方案',exact:true}).click()
 await page.getByRole('textbox',{name:'方案名称',exact:true}).fill('Bench多选试点')
 await page.getByRole('button',{name:'保存',exact:true}).click()
 await page.getByRole('button',{name:'清空筛选',exact:true}).click()
 await expect(page.getByText('共 125 条',{exact:true})).toBeVisible()
 const beforeRestore=requests.length
 await pick('查询方案','Bench多选试点')
 await settle();assert.equal(requests.length,beforeRestore,'加载方案不能自动查询')
 await page.getByRole('button',{name:'查询',exact:true}).click()
 await expect(page.getByText('共 63 条',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:/添加筛选/}).click()
 await pick('条件1字段','项目名称');await pick('条件1匹配方式','不包含')
 await page.getByRole('textbox',{name:'条件1值',exact:true}).fill('Pump')
 await panel.getByRole('button',{name:'应用条件',exact:true}).click()
 await expect(page.getByText('共 41 条',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:/添加筛选/}).click()
 await pick('条件1字段','数量');await pick('条件1匹配方式','区间')
 await page.getByRole('spinbutton',{name:'条件1值',exact:true}).fill('20')
 await page.getByRole('spinbutton',{name:'条件1结束值',exact:true}).fill('0')
 const beforeInvalid=requests.length
 await panel.getByRole('button',{name:'应用条件',exact:true}).click()
 await expect(page.getByText('最小值不能大于最大值',{exact:true})).toBeVisible()
 assert.equal(requests.length,beforeInvalid)
 await page.getByRole('spinbutton',{name:'条件1值',exact:true}).fill('0')
 await page.getByRole('spinbutton',{name:'条件1结束值',exact:true}).fill('0')
 await panel.getByRole('button',{name:'应用条件',exact:true}).click()
 await expect(page.getByText('共 42 条',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:/添加筛选/}).click()
 await pick('条件1匹配方式','为空')
 assert.equal(await page.getByRole('spinbutton',{name:'条件1值',exact:true}).count(),0)
 await pick('条件1字段','计划开始');await pick('条件1匹配方式','区间')
 await panel.getByPlaceholder('选择日期',{exact:true}).click()
 await expect(page.locator('.el-date-picker:visible')).toBeVisible()
 await page.locator('.el-date-picker:visible .el-date-table td.available').first().click()
 await expect(panel).toBeVisible()
 await panel.getByPlaceholder('结束日期',{exact:true}).fill('2026-10-10')
 await panel.getByPlaceholder('结束日期',{exact:true}).press('Escape')
 await expect(page.locator('.el-date-picker:visible')).toHaveCount(0)
 await panel.getByRole('button',{name:'取消',exact:true}).press('Escape')
 await expect(panel).not.toBeVisible()
 assert.equal(JSON.parse(requests.at(-1).filters)[0].field,'quantity','Esc保留原应用条件')
 const beforeOld=requests.length
 await pick('查询方案','旧方案兼容');await settle()
 assert.equal(requests.length,beforeOld)
 assert.equal(Math.round(await page.locator('.ag-header-cell[col-id="project_name"]').evaluate(e=>e.getBoundingClientRect().width)),190,'待查询时不改列宽')
 await page.getByRole('button',{name:'查询',exact:true}).click()
 await expect(page.getByText('共 84 条',{exact:true})).toBeVisible()
 assert.equal(requests.at(-1).page_size,'20');assert.equal(requests.at(-1).page,'1')
 assert.equal(JSON.parse(requests.at(-1).filters)[0].schemaVersion,1)
 assert.equal(Math.round(await page.locator('.ag-header-cell[col-id="project_name"]').evaluate(e=>e.getBoundingClientRect().width)),245,'查询方案恢复列宽')
 const beforeStale=requests.length
 await pick('查询方案','失效字段方案')
 await expect(page.getByText('筛选字段已失效，请重新选择',{exact:true})).toBeVisible()
 assert.equal(requests.length,beforeStale)
 await page.getByRole('button',{name:'2',exact:true}).click()
 await expect.poll(()=>requests.at(-1).page).toBe('2')
 assert.equal(JSON.parse(requests.at(-1).filters)[0].field,'project_name','失效方案不扩大当前查询')
 await page.getByRole('button',{name:'清空筛选',exact:true}).click()
 await expect(page.getByText('共 125 条',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:/添加筛选/}).click()
 await panel.getByRole('button',{name:'增加条件',exact:true}).click()
 await pick('条件1字段','负责人');await pick('条件1匹配方式','不等于');await pick('条件1值','历史负责人')
 await panel.getByRole('button',{name:'应用条件',exact:true}).click()
 await expect(page.getByText('共 124 条',{exact:true})).toBeVisible()
 await page.getByRole('button',{name:'2',exact:true}).click()
 await expect.poll(()=>requests.at(-1).page).toBe('2')
 assert.equal(JSON.parse(requests.at(-1).filters)[0].value,'历史负责人','历史人员离开结果页后仍可筛选翻页')
 await page.screenshot({path:'../.runtime/unified-archive-query-pilot.png',fullPage:true})
 assert.deepEqual(errors,[])
 console.log('archive unified query browser passed: typed panel, cancel/apply, pages, saved/legacy plans and widths, invalid field, zero, interval, date/Esc, multiselect bounds at 1920/1182/390')
}catch(e){console.error({url:page.url(),errors,requests});await page.screenshot({path:'../.runtime/unified-archive-query-failure.png',fullPage:true});throw e}
finally{await browser.close()}
