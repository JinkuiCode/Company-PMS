import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const base='http://127.0.0.1:5174'
const out='../outputs/archive-draft-management-20261016/quantity'
fs.mkdirSync(out,{recursive:true})
const browser=await chromium.launch({channel:'msedge',headless:true})
try {
 const page=await browser.newPage({viewport:{width:1366,height:850}})
 page.setDefaultTimeout(8000)
 const writes=[],errors=[];let previews=0
 const row={id:1,project_code:'LOCAL-QUANTITY-1',project_name:'数量规则验收',archive_category:1,customer:'验收客户',business_product_line_id:7,product_line_id:7,quantity:-1,quantity_unit:7,manager_id:42,manager_name:'负责人',machine_model:1,equipment_series:1,serial_no:'SN',is_enabled:1,data_origin:'pms',erp_sync_policy:'manual',created_at:'2026-10-16T01:00:00',can_edit:false,can_maintain:true,change_mode:'readonly',change_version:'a'.repeat(64),contract_signed_date:'2026-10-01',contract_ship_date:'2026-12-01'}
 const keys=['archive_category','project_code','project_name','customer','product_line_id','quantity','quantity_unit','manager_id','machine_model','equipment_series','serial_no','contract_signed_date','contract_ship_date','remarks']
 const diff=[{field_key:'product_line_id',field_label:'产品线',before_display:'-',after_display:'8吋Bench',after_name_source:'current'},{field_key:'quantity',field_label:'数量',before_display:'-1',after_display:'1'},{field_key:'manager_id',field_label:'负责人',before_display:'-',after_display:'负责人（LOCAL）',after_name_source:'current'}]
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-ui-fixture'))
 page.on('pageerror',e=>errors.push(e.message))
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url()),path=url.pathname,method=route.request().method()
  if(url.origin!==base)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  let body=[]
  if(path==='/api/auth/me')body={id:1,username:'fixture',real_name:'本机验收',permissions:['project:archive:view','project:archive:add','project:archive:edit','project:archive:maintain','system:operation-log:view']}
  else if(path==='/api/users/options')body=[{id:42,real_name:'负责人',username:'LOCAL'}]
  else if(path==='/api/product-lines/options'||path==='/api/product-lines/labels'||path==='/api/form-drafts/archive-create/product-lines')body={options:[{value:7,label:'8吋Bench'}],label_map:{7:'8吋Bench'}}
  else if(path==='/api/projects/archives/fields')body={items:keys.map(field_key=>({field_key,label:field_key,visible:true,editable:true,list_available:true,required:false}))}
  else if(path.startsWith('/api/dicts/code/'))body={items:[{value:1,label:'主机'},{value:7,label:'台'}],label_map:{1:'主机',7:'台'}}
  else if(path==='/api/projects/archives/list')body={total:1,items:[row]}
  else if(path==='/api/projects/archives/1/maintenance/preview'){
   previews++;const updates=route.request().postDataJSON().updates
   body={mode:'maintenance',expected_version:row.change_version,differences:Object.keys(updates).map(key=>({field_key:key,field_label:key==='quantity'?'数量':'备注',before_display:String(row[key]??'-'),after_display:String(updates[key])}))}
  }
  else if(path==='/api/projects/archives/1/maintenance'&&method==='PUT'){
   const payload=route.request().postDataJSON();writes.push(payload);Object.assign(row,payload.updates);row.change_version='b'.repeat(64);body={mode:'maintenance',sync_queued:false}
  }
  else if(path==='/api/document-history/archive/1')body={total:1,actions:[],items:[{id:1,actor:'本机验收',created_at:'2026-10-16T10:00:00',action:'maintain',action_label:'维护',status:'success',status_label:'成功',source:'项目档案',summary:'数量纠正',diff_items:diff}]}
  return route.fulfill({json:body})
 })
 await page.goto(base+'/project/archive')
 await page.getByRole('button',{name:'新增档案',exact:true}).click()
 const create=page.getByRole('dialog',{name:'新增项目档案',exact:true})
 for(const value of ['0','-1','1.5']) {
  await create.getByRole('spinbutton',{name:'数量',exact:true}).fill(value)
  await create.getByRole('button',{name:'正式保存',exact:true}).click()
  await expect(create).toContainText('数量只允许填写正整数')
  await expect(create.getByRole('spinbutton',{name:'数量',exact:true})).toHaveValue(value)
  assert.equal(writes.length,0)
 }
 await page.screenshot({path:out+'/create-quantity-validation.jpg'})
 async function open(){
  await page.goto(base+'/project/archive')
  await page.getByRole('button',{name:'查看',exact:true}).click()
  await page.getByRole('button',{name:'维护',exact:true}).click()
  const drawer=page.getByRole('dialog',{name:'维护项目档案',exact:true})
  await expect(drawer.getByRole('spinbutton',{name:'数量',exact:true})).toHaveValue('-1')
  return drawer
 }
 for(const value of ['0','-2','1.5']){
  const drawer=await open(),before=previews
  await drawer.getByRole('spinbutton',{name:'数量',exact:true}).fill(value)
  await drawer.getByRole('textbox',{name:'项目名称',exact:true}).click()
  await expect(drawer.getByRole('spinbutton',{name:'数量',exact:true})).toHaveValue(value)
  await drawer.getByRole('button',{name:'确认维护',exact:true}).click()
  await expect(drawer).toContainText('数量只允许填写正整数')
  assert.equal(previews,before);assert.equal(writes.length,0)
 }
 let drawer=await open()
 await drawer.getByRole('textbox',{name:'备注',exact:true}).fill('历史数量未变，仅维护备注')
 await drawer.getByRole('button',{name:'确认维护',exact:true}).click()
 const confirm=page.getByRole('dialog',{name:'确认档案维护',exact:true})
 await expect(confirm).toBeVisible();await expect(confirm.getByRole('cell',{name:'数量',exact:true})).toHaveCount(0)
 await confirm.getByRole('button',{name:'返回修改',exact:true}).click()
 await drawer.getByRole('spinbutton',{name:'数量',exact:true}).fill('1')
 await drawer.getByRole('textbox',{name:'备注',exact:true}).fill('')
 await drawer.getByRole('button',{name:'确认维护',exact:true}).click()
 await expect(confirm).toContainText('-1');await expect(confirm).toContainText('1')
 await confirm.getByRole('textbox',{name:'维护原因',exact:true}).fill('本机隔离验收：纠正负数')
 await confirm.getByRole('button',{name:'确认生效',exact:true}).click()
 await expect(confirm).toBeHidden();assert.equal(writes.length,1);assert.deepEqual(writes[0].updates,{quantity:1})
 drawer=page.getByRole('dialog',{name:'查看项目档案',exact:true})
 await expect(drawer.getByRole('spinbutton',{name:'数量',exact:true})).toHaveValue('1')
 await drawer.getByRole('tab',{name:'操作记录',exact:true}).click()
 await drawer.getByRole('button',{name:/查看 3 项字段变化/}).click()
 const table=drawer.getByRole('table',{name:'字段变化'})
 await expect(table).toContainText('8吋Bench');await expect(table).not.toContainText('当前名称')
 assert.deepEqual(await table.locator('tbody th').allTextContents(),['产品线','数量','负责人'])
 await expect(drawer.locator('.history-name-note')).not.toContainText('编号')
 await drawer.getByText('名称说明',{exact:true}).click()
 await expect(drawer.locator('.history-name-note')).toContainText('显示当前关联名称')
 await page.screenshot({path:out+'/document-log-and-quantity.jpg'})
 assert.deepEqual(errors,[])
 console.log('PASS: 0/负数/小数拒绝且未静默改值；旧-1未变可维护；仅quantity=1提交；日志顺序及按需名称说明；真实业务API写入0')
}finally{await browser.close()}
