import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
const base=process.env.PMS_GOVERNANCE_URL||'http://127.0.0.1:5174'
const browser=await chromium.launch({channel:'msedge',headless:true})
try{
 const page=await browser.newPage({viewport:{width:1366,height:768}});page.setDefaultTimeout(8000)
 let namesFail=false,optionsFail=true,labelCalls=0,optionCalls=0
 const writes=[],errors=[]
 const row={id:1,project_code:'LABEL-001',project_name:'名称显示验收',product_line_id:3,
  archive_category:1,is_enabled:1,manager_id:42,manager_name:'负责人',can_edit:false,
  can_maintain:true,change_mode:'readonly',change_version:'a'.repeat(64),erp_sync_policy:'manual',
  data_origin:'offline_initial',remarks:'不修改',created_at:'2020-01-01'}
 await page.addInitScript(()=>{
  localStorage.setItem('access_token','isolated-fixture-only')
  localStorage.setItem('pms_project_archive_list_columns_v2:99',JSON.stringify({selected_column_keys:['project_code','project_name','product_line_id'],columnState:[]}))
 })
 page.on('pageerror',error=>errors.push(error.message))
 await page.route('**/*',async route=>{
  const u=new URL(route.request().url()),path=u.pathname
  if(u.origin!==base)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  if(['POST','PUT','DELETE','PATCH'].includes(route.request().method()))writes.push(path)
  let body=[]
  if(path==='/api/auth/me')body={id:99,username:'labels-fixture',permissions:['project:archive:view','project:archive:add','project:archive:edit','project:archive:maintain']}
  else if(path==='/api/users/options')body=[{id:42,real_name:'负责人'}]
  else if(path==='/api/product-lines/labels'){
   labelCalls++
   if(namesFail)return route.fulfill({status:503,json:{detail:'名称读取失败'}})
   body={label_map:{3:'12吋Bench',4:'Single',5:'另一历史产品线'}}
  }else if(path==='/api/product-lines/options'){
   optionCalls++
   if(optionsFail)return route.fulfill({status:503,json:{detail:'金蝶组织目录暂不可用，请稍后重试'}})
   body={options:[{value:4,label:'Single'}],label_map:{3:'12吋Bench',4:'Single',5:'另一历史产品线'}}
  }else if(path==='/api/projects/archives/fields')body={items:['archive_category','project_code','project_name','product_line_id','manager_id','remarks'].map(field_key=>({field_key,visible:true,editable:true,list_available:true,required:false}))}
  else if(path==='/api/projects/archives/list')body={items:[row],total:1}
  else if(path.startsWith('/api/dicts/code/'))body={items:[{value:1,label:'主机'}],label_map:{1:'主机'}}
  else if(path==='/api/offline-archives/initialization-status')body={enabled:false}
  await route.fulfill({json:body})
 })
 async function open(){await page.goto(`${base}/project/archive`);await page.getByRole('button',{name:'查看',exact:true}).click()}
 function lineField(){return page.locator('.pms-form-field').filter({has:page.getByRole('combobox',{name:'产品线',exact:true})})}
 await open()
 await expect(lineField()).toContainText('12吋Bench')
 await page.getByRole('button',{name:'维护',exact:true}).click()
 await expect(page.getByRole('combobox',{name:'产品线',exact:true})).toBeDisabled()
 await expect(page.getByRole('textbox',{name:'备注',exact:true})).toBeEditable()
 await expect(page.getByRole('status').filter({hasText:'产品线选项暂不可用'})).toBeVisible()
 await page.screenshot({path:'../outputs/product-line-display-20261015/isolated-name-offline.jpg'})
 await page.getByRole('button',{name:'取消',exact:true}).click()
 await page.getByRole('button',{name:'新增档案',exact:true}).click()
 await expect(page.getByRole('dialog',{name:'新增项目档案',exact:true})).toHaveCount(0)
 optionsFail=false
 await page.getByRole('button',{name:'查看',exact:true}).click()
 await page.getByRole('button',{name:'维护',exact:true}).click()
 await page.getByRole('button',{name:'重试产品线选项',exact:true}).click()
 await expect(page.getByRole('combobox',{name:'产品线',exact:true})).toBeEnabled()
 await lineField().locator('.el-select').click()
 await expect(page.getByRole('option',{name:'12吋Bench',exact:true})).toHaveAttribute('aria-disabled','true')
 await expect(page.getByRole('option',{name:'Single',exact:true})).toBeVisible()
 await expect(page.getByRole('option',{name:'另一历史产品线',exact:true})).toHaveCount(0)
 await page.getByRole('combobox',{name:'产品线',exact:true}).press('Escape')
 namesFail=true;await open()
 await expect(page.getByRole('alert').filter({hasText:'产品线名称加载失败'})).toBeVisible()
 await expect(lineField()).toContainText('名称暂不可用')
 await expect(page.locator('.ag-cell[col-id="product_line_id"]')).toHaveText('名称暂不可用')
 const beforeChoices=optionCalls,beforeNames=labelCalls
 namesFail=false
 await page.getByRole('button',{name:'重试产品线名称',exact:true}).click()
 await expect(lineField()).toContainText('12吋Bench')
 await expect(page.locator('.ag-cell[col-id="product_line_id"]')).toHaveText('12吋Bench')
 assert.equal(optionCalls,beforeChoices,'display retry must not call the ERP choice API')
 assert.equal(labelCalls,beforeNames+1)
 await page.setViewportSize({width:518,height:671})
 await expect(lineField()).toContainText('12吋Bench')
 await page.screenshot({path:'../outputs/product-line-display-20261015/isolated-name-narrow.jpg'})
 assert.deepEqual(writes,[])
 assert.deepEqual(errors,[])
 console.log('PASS: 独立名称、503保持只读、新增拒绝、当前禁用项、独立重试与窄窗；零写入')
}finally{await browser.close()}
