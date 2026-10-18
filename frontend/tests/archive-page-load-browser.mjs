import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const base='http://127.0.0.1:5174',out='../outputs/governance-form-session-20261016'
fs.mkdirSync(out,{recursive:true})
const browser=await chromium.launch({channel:'msedge',headless:true})
try{
 const page=await browser.newPage({viewport:{width:1366,height:850}});page.setDefaultTimeout(8000)
 await page.addInitScript(()=>{
  localStorage.setItem('access_token','isolated-page-load')
  localStorage.setItem('pms_project_archive_list_columns_v2:1',JSON.stringify({selected_column_keys:['customer'],columnState:[{colId:'project_name',sort:'asc',sortIndex:0},{colId:'project_code',width:245}]}))
 })
 const errors=[];page.on('pageerror',e=>errors.push(e.message))
 const pending=[];let mode='initial',listRequests=0,lastSort,lastFilters
 const row=name=>({id:1,project_code:name,project_name:name,is_enabled:1,can_edit:false})
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url()),path=url.pathname
  if(url.origin!==base)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  let body=[]
  if(path==='/api/auth/me')body={id:1,username:'fixture',real_name:'本机验收',permissions:['project:archive:view']}
  else if(path==='/api/product-lines/options'||path==='/api/product-lines/labels')body={options:[],label_map:{}}
  else if(path==='/api/projects/archives/fields')body={items:[]}
  else if(path.startsWith('/api/dicts/code/'))body={items:[{value:1,label:'主机'}],label_map:{1:'主机'}}
  else if(path==='/api/projects/archives/list'){
   listRequests++;lastSort=JSON.parse(url.searchParams.get('sort')||'[]');lastFilters=JSON.parse(url.searchParams.get('filters')||'[]')
   if(mode==='hold'){pending.push(route);return}
   if(mode==='fail')return route.fulfill({status:503,json:{detail:'隔离验收模拟加载失败'}})
   body={total:mode==='empty'?0:1,items:mode==='empty'?[]:[row(mode==='initial'?'INITIAL':'RETRY-SUCCESS')]}
  }
  return route.fulfill({json:body})
 })
 await page.goto(base+'/project/archive');await expect(page.getByText('INITIAL',{exact:true}).first()).toBeVisible()
 assert.equal(Math.round(await page.locator('.ag-header-cell[col-id="project_code"]').evaluate(el=>el.getBoundingClientRect().width)),245,'共享存储仍须恢复原用户列宽')
 assert.deepEqual(lastSort,[{colId:'project_code',sort:'desc'}],'旧名称排序不得覆盖已确认的编码倒序')
 assert.deepEqual(lastFilters.find(item=>item.field==='archive_category')?.value,[1],'默认仍按主机查询')
 async function query(count=1){await page.getByRole('button',{name:'查询',exact:true}).evaluate((el,count)=>{
   let vm=el.__vueParentComponent;while(vm&&!vm.setupState?.fetchList)vm=vm.parent
   if(!vm)throw new Error('真实档案查询入口缺失')
   for(let i=0;i<count;i++)vm.setupState.fetchList()
  },count)}
 mode='hold';await query(2);await expect.poll(()=>pending.length).toBe(2)
 await pending[1].fulfill({json:{total:1,items:[row('NEW-RESPONSE')]}})
 await expect(page.getByText('NEW-RESPONSE',{exact:true}).first()).toBeVisible()
 await pending[0].fulfill({json:{total:1,items:[row('OLD-RESPONSE')]}})
 await expect(page.getByText('OLD-RESPONSE',{exact:true})).toHaveCount(0)
 await expect(page.getByText('NEW-RESPONSE',{exact:true}).first()).toBeVisible()
 mode='fail';await query();const alert=page.locator('.pms-list-load-error')
 await expect(alert).toContainText('加载失败');await expect(page.getByText('NEW-RESPONSE',{exact:true})).toHaveCount(0)
 mode='ready';await alert.getByRole('button',{name:'重试',exact:true}).click()
 await expect(alert).toBeHidden();await expect(page.getByText('RETRY-SUCCESS',{exact:true}).first()).toBeVisible()
 mode='empty';await query();await expect(page.getByText('RETRY-SUCCESS',{exact:true})).toHaveCount(0)
 await expect(page.locator('.el-loading-mask')).toHaveCount(0);await expect(alert).toBeHidden()
 await page.screenshot({path:out+'/page-empty.jpg'})
 mode='hold';await query();await expect.poll(()=>pending.length).toBe(3)
 await page.getByRole('button',{name:'查询',exact:true}).evaluate(async el=>{
  let vm=el.__vueParentComponent;while(vm&&!vm.setupState?.fetchList)vm=vm.parent
  window.fixtureRouter=vm.proxy.$router;await window.fixtureRouter.push('/login')
 })
 await expect(page).toHaveURL(base+'/login')
 mode='ready';await page.evaluate(()=>window.fixtureRouter.push('/project/archive'))
 await expect(page.getByText('RETRY-SUCCESS',{exact:true}).first()).toBeVisible()
 await pending[2].fulfill({json:{total:1,items:[row('OLD-AFTER-LEAVE')]}})
 await expect(page.getByText('OLD-AFTER-LEAVE',{exact:true})).toHaveCount(0)
 const prefKey='pms_project_archive_list_columns_v2:1'
 await page.evaluate(key=>localStorage.setItem(key,JSON.stringify({schema_version:99,keep:'未来版本偏好'})),prefKey)
 await page.getByRole('button',{name:'查询',exact:true}).evaluate(async el=>{
   let vm=el.__vueParentComponent;while(vm&&!vm.setupState?.submitArchiveQuery)vm=vm.parent
   await vm.setupState.submitArchiveQuery([],{columns:{selected_column_keys:['customer'],columnState:[{colId:'customer',width:207}]}})
 })
 assert.equal(await page.evaluate(key=>JSON.parse(localStorage.getItem(key)).schema_version,prefKey),99,'查询方案不得绕过未来版本保护')
 mode='ready'
 await page.evaluate(key=>{localStorage.removeItem(key);window.fixtureDeniedWrites=0;const original=Storage.prototype.setItem;Storage.prototype.setItem=function(k,v){if(k===key){window.fixtureDeniedWrites++;throw new Error('隔离模拟存储拒绝')}return original.call(this,k,v)}},prefKey)
 const beforeDeniedQuery=listRequests
 await page.getByRole('button',{name:'查询',exact:true}).evaluate(async el=>{
   let vm=el.__vueParentComponent;while(vm&&!vm.setupState?.submitArchiveQuery)vm=vm.parent
   await vm.setupState.submitArchiveQuery([],{columns:{selected_column_keys:['customer'],columnState:[{colId:'customer',width:207}]}})
 })
 await expect.poll(()=>listRequests).toBeGreaterThan(beforeDeniedQuery)
 assert.ok(await page.evaluate(()=>window.fixtureDeniedWrites)>0,'必须实际命中模拟存储异常')
 await expect(page.getByText('RETRY-SUCCESS',{exact:true}).first()).toBeVisible()

 assert.deepEqual(errors,[])
 console.log('PASS: 旧响应晚到不覆盖新列表；加载失败清理数据并显示重试；重试恢复；空结果停止加载；卸载重进后旧响应丢弃；查询方案保护未来版本且存储失败不阻断查询；所有API模拟、真实写入0')
}finally{await browser.close()}
