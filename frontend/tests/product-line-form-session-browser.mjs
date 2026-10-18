import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
const base=process.env.PMS_PROGRESS_TEST_BASE||'http://127.0.0.1:5198'
assert.equal(new URL(base).hostname,'127.0.0.1')
const browser=await chromium.launch({channel:'msedge',headless:true})
try {
 const page=await browser.newPage({viewport:{width:1366,height:850}})
 const writes=[],pending=[],errors=[]
 const fixture={id:1,organization_id:100,organization_code:'TEST-ORG',organization_name:'隔离组织',display_name:'隔离产品线',sort:1,is_enabled:true,updated_at:'2026-10-18T00:00:00'}
 page.on('pageerror',e=>errors.push(e.message))
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-product-line-session'))
 await page.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname
  if(url.origin!==base)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  let body=[]
  if(path==='/api/auth/me')body={id:1,username:'fixture',permissions:['system:product-line:view','system:product-line:add','system:product-line:edit','system:product-line:delete']}
  else if(req.method()!=='GET'){
   writes.push({method:req.method(),path,body:req.postDataJSON()})
   assert.ok((req.method()==='PUT'&&path==='/api/product-lines/1')||(req.method()==='POST'&&path==='/api/product-lines'),`unexpected mocked write ${path}`)
   pending.push(route);return
  } else if(path==='/api/product-lines')body={items:[fixture],total:1}
  else if(path==='/api/product-lines/organizations')body={items:[{organization_id:100,code:'TEST-ORG',name:'隔离组织'}],total:1}
  return route.fulfill({json:body})
 })
 await page.goto(base+'/system/product-line')
 await expect(page.getByText('隔离产品线',{exact:true}).first()).toBeVisible()
 await page.getByRole('button',{name:'编辑',exact:true}).click()
 const name=page.getByRole('textbox',{name:'产品线名称',exact:true})
 await expect(name).toHaveValue('隔离产品线')
 const invoke=async(method,count=1)=>page.getByRole('button',{name:'查询',exact:true}).evaluate((el,{method,count})=>{
  let vm=el.__vueParentComponent;while(vm&&vm.type.__name!=='ProductLineList')vm=vm.parent
  window.lineVm=vm;window.lineRequests||=[]
  for(let i=0;i<count;i++)window.lineRequests.push(vm.setupState[method]())
 },{method,count})
 await name.fill('尚未保存')
 await invoke('close',2)
 const confirmations=page.getByRole('dialog').filter({hasText:'放弃尚未保存的产品线修改？'})
 await expect(confirmations).toHaveCount(1)
 await invoke('save')
 assert.equal(writes.length,0,'关闭确认期间不得保存')
 await confirmations.getByRole('button',{name:'取消',exact:true}).click()
 await page.evaluate(()=>Promise.all(window.lineRequests))
 await expect(name).toHaveValue('尚未保存')
 await page.getByRole('button',{name:'取消',exact:true}).last().click()
 await confirmations.getByRole('button',{name:'确定',exact:true}).click()
 await expect(name).toHaveCount(0)
 await page.getByRole('button',{name:'编辑',exact:true}).click()
 await name.fill('')
 await page.getByRole('button',{name:'保存',exact:true}).click()
 await expect(page.getByText('请选择金蝶组织并填写产品线名称',{exact:true})).toBeVisible()
 assert.equal(writes.length,0)
 await name.fill('修改后名称')
 await invoke('save',2)
 await expect.poll(()=>writes.length).toBe(1)
 await expect(name).toBeDisabled()
 await expect(page.getByRole('button',{name:'取消',exact:true}).last()).toBeDisabled()
 await invoke('close')
 await page.evaluate(()=>window.lineVm.proxy.$router.push('/login'))
 assert.equal(new URL(page.url()).pathname,'/system/product-line','保存中禁止离页')
 assert.deepEqual(writes[0],{method:'PUT',path:'/api/product-lines/1',body:{display_name:'修改后名称',sort:1,is_enabled:true,expected_updated_at:fixture.updated_at}})
 await pending[0].fulfill({status:409,json:{detail:'隔离模拟版本冲突'}})
 await page.evaluate(()=>Promise.all(window.lineRequests))
 await expect(name).toBeEnabled();await expect(name).toHaveValue('修改后名称')
 await expect(page.getByText('名称、组织冲突或记录已被修改，请关闭并刷新后重试',{exact:true})).toBeVisible()
 await page.screenshot({path:'../outputs/product-line-form-session-20261018/conflict.png'})
 await page.getByRole('button',{name:'保存',exact:true}).click()
 await expect.poll(()=>writes.length).toBe(2)
 await pending[1].fulfill({json:{...fixture,display_name:'修改后名称'}})
 await expect(name).toHaveCount(0)
 await page.getByRole('button',{name:'新增产品线',exact:true}).click()
 await expect(page.getByRole('combobox',{name:'金蝶组织',exact:true})).toBeEnabled()
 await page.locator('.pms-form-field').filter({has:page.locator('#organization')}).locator('.el-select__wrapper').click()
 await page.getByRole('option',{name:'TEST-ORG · 隔离组织',exact:true}).click()
 await name.fill('新增隔离产品线')
 await page.getByRole('button',{name:'保存',exact:true}).click()
 await expect.poll(()=>writes.length).toBe(3)
 assert.deepEqual(writes[2],{method:'POST',path:'/api/product-lines',body:{display_name:'新增隔离产品线',sort:0,organization_id:100}})
 await pending[2].fulfill({json:{...fixture,id:2}})
 await expect(name).toHaveCount(0)
 await page.getByRole('button',{name:'编辑',exact:true}).click()
 await page.evaluate(()=>window.lineVm.appContext.config.globalProperties.$pinia._s.get('auth').user.permissions=['system:product-line:view'])
 await invoke('save');await page.evaluate(()=>Promise.all(window.lineRequests))
 assert.equal(writes.length,3,'缺编辑权限不调用写接口')
 assert.deepEqual(errors,[])
 console.log('PASS product-line form: one close confirmation, confirmation/save mutex, validation, busy input/route lock, 409 preserves input, retry, immutable organization, original POST/PUT and no-permission rejection; every API mocked')
} finally {await browser.close()}
