import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
const origin=process.env.PMS_TEST_ORIGIN||'http://127.0.0.1:5194'
const browser=await chromium.launch({channel:'msedge',headless:true})
try{
 const page=await browser.newPage({viewport:{width:1440,height:900}})
 const errors=[],writes=[]
 let rejected=true,uploads=0,syncs=0,applied=0
 let privileged=true
 const row={id:1,project_code:'AS-DEMO-1',project_name:null,customer:'原客户',quantity:0,
  archive_category:1,data_origin:'offline_initial',erp_sync_policy:'manual',product_line_id:null,
  address_detail:'历史地点原文',address_province:null,address_city:null,
  created_at:'2026-09-24T10:00:00',updated_at:'2026-09-24T10:00:00',is_enabled:1}
 const fields=['project_code','project_name','customer','manager_id','equipment_series','serial_no',
 'product_line_id','contract_signed_date','contract_ship_date','actual_ship_date','warranty_end_date',
 'address_province','address_city','address_detail','project_contact','contact_phone','plan_start_date','plan_end_date',
 'archive_category','customer_full_name','machine_model','quantity','quantity_unit','sales_company','legacy_archive_status',
 'legacy_code_date','legacy_updated_date','delivery_note','remarks']
 page.on('pageerror',e=>errors.push(e.message))
 await page.addInitScript(()=>localStorage.setItem('access_token','mock-only'))
 await page.route('**/*',async route=>{
  const req=route.request(),url=new URL(req.url()),path=url.pathname
  if(url.origin!==origin)return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  let body=[]
  if(path==='/api/auth/me')body={id:42,username:'test',real_name:'测试人',permissions:['project:archive:view','project:archive:edit',...(privileged?['project:archive:import','project:archive:assign-line','project:archive:sync','business:data:all']:[])]}
  else if(path==='/api/product-lines/options')body={options:[{value:7,label:'测试产品线'}],label_map:{7:'测试产品线'}}
  else if(path==='/api/projects/archives/fields')body={items:fields.map(field_key=>({field_key,label:field_key,visible:true,editable:field_key!=='project_code',list_available:true,required:['project_name','product_line_id','contract_signed_date'].includes(field_key)}))}
  else if(path==='/api/projects/archives/list')body={items:[row],total:1}
  else if(path==='/api/projects/archives/regions')body=[]
  else if(path.startsWith('/api/dicts/code/'))body={items:[{value:1,label:'AS类'}],label_map:{1:'AS类'}}
  else if(path==='/api/offline-archives/archives/1/source')body={batch_id:5,source_id:'S5-R12',source_sheet:'售后',source_row:12,original_code:'A-DEMO'}
  else if(path==='/api/projects/archives/1'&&req.method()==='PUT'){
   writes.push(req.postDataJSON());Object.assign(row,req.postDataJSON());body={sync_queued:false}
  }
  else if(path==='/api/erp/archives/1/submit'){syncs++;return route.fulfill({status:422,json:{detail:'请先分配产品线后再同步'}})}
  else if(path==='/api/offline-archives/workbook'){uploads++;body={payload:{rows:[]},errors:[]}}
  else if(path==='/api/offline-archives/preview')body={total:3024,errors:rejected?[{source_id:'S5-R12',message:'项目编号与现有档案重复'}]:[],already_imported:false}
  else if(path==='/api/offline-archives/apply'){applied++;body={batch_id:9,created:3024,msg:'已归档，未发送金蝶'}}
  await route.fulfill({json:body})
 })
 await page.goto(origin+'/project/archive')
 await page.getByRole('button',{name:'编辑',exact:true}).click()
 const drawer=page.locator('.archive-edit-drawer')
 await expect(drawer).toContainText('仅手动同步')
 await expect(drawer).toContainText('原表第 12 行')
 await expect(drawer).toContainText('A-DEMO')
 await expect(drawer.getByRole('button',{name:'编辑产品类别',exact:true})).toHaveCount(0)
 await expect(drawer.getByRole('button',{name:'编辑数量',exact:true})).toHaveText('0')
 await drawer.getByRole('button',{name:'编辑客户',exact:true}).click()
 await drawer.locator('#archive-drawer-customer').fill('新客户')
 await drawer.getByRole('button',{name:/保存修改/}).click()
 await page.screenshot({path:'/private/tmp/pms-offline-edit-check.png'})
 await expect.poll(()=>writes.length).toBe(1)
 assert.deepEqual(writes[0],{customer:'新客户'})
 assert.equal(syncs,0)
 await drawer.getByRole('button',{name:'同步金蝶',exact:true}).click()
 await expect(page.getByText('请先分配产品线后再同步')).toBeVisible()
 assert.equal(syncs,1)
 await drawer.getByRole('button',{name:'关闭档案编辑',exact:true}).click()
 await page.getByRole('button',{name:'期初导入',exact:true}).click()
 const imports=page.locator('.pms-form-drawer:visible')
 await imports.locator('input[type=file]').setInputFiles({name:'test.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:Buffer.from('mock')})
 await expect(imports).toContainText('项目编号与现有档案重复')
 await expect(imports.getByRole('button',{name:'确认导入',exact:true})).toBeDisabled()
 rejected=false
 await imports.locator('input[type=file]').setInputFiles({name:'approved.xlsx',mimeType:'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',buffer:Buffer.from('mock2')})
 await expect(imports.getByRole('button',{name:'确认导入',exact:true})).toBeEnabled()
 await imports.getByRole('button',{name:'确认导入',exact:true}).click()
 await expect(imports).toContainText('导入批次：9')
 await expect(imports.getByRole('button',{name:'确认导入',exact:true})).toBeDisabled()
 assert.equal(applied,1);assert.equal(uploads,2)
 await page.screenshot({path:'/private/tmp/pms-offline-import.png'})
 await imports.getByRole('button',{name:'关闭',exact:true}).click()
 privileged=false
 await page.reload()
 await expect(page.getByRole('button',{name:'期初导入',exact:true})).toHaveCount(0)
 await expect(page.getByRole('button',{name:'分配产品线',exact:true})).toHaveCount(0)
 await page.getByRole('button',{name:'编辑',exact:true}).click()
 await expect(drawer.getByRole('button',{name:'同步金蝶',exact:true})).toHaveCount(0)
 assert.deepEqual(errors,[])
 console.log('Offline browser passed: empty historical fields, zero, manual sync, source trace, errors, import disable/apply, permissions')
}finally{await browser.close()}
