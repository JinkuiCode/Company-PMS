import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
const browser=await chromium.launch({channel:'msedge',headless:true})
try{
 const page=await browser.newPage({viewport:{width:1366,height:768}});page.setDefaultTimeout(8000)
 const writes=[],errors=[];let submitted=false,actor=42,status=2,failDecision=false
 const row={id:1,project_code:'GOV-001',project_name:'正式名称',archive_category:1,customer:'客户',product_line_id:7,quantity:1,quantity_unit:7,manager_id:42,manager_name:'项目负责人',machine_model:1,equipment_series:1,serial_no:'SN',is_enabled:1,data_origin:'offline_initial',erp_sync_policy:'manual',created_at:'2026-10-14T12:00:00',can_edit:true,change_mode:'approval',change_version:'a'.repeat(64),approver_id:43,approver_name:'部门负责人（A002）',contract_signed_date:'2026-10-01',contract_ship_date:'2026-12-01'}
 const names=['archive_category','project_code','project_name','customer','product_line_id','quantity','quantity_unit','manager_id','machine_model','equipment_series','serial_no','customer_full_name','contract_signed_date','contract_ship_date','remarks','project_contact','created_at']
 await page.addInitScript(()=>localStorage.setItem('access_token','mock-only'))
 page.on('pageerror',e=>errors.push(e.message))
 await page.route('**/*',async route=>{
  const url=new URL(route.request().url()),path=url.pathname,method=route.request().method()
  if(url.origin!=='http://127.0.0.1:5174')return route.abort()
  if(!path.startsWith('/api/'))return route.continue()
  let body=[]
  if(path==='/api/auth/me')body={id:actor,username:actor===42?'A001':'A002',real_name:actor===42?'项目负责人':'部门负责人',permissions:['project:archive:view','project:archive:add','project:archive:edit']}
  else if(path==='/api/users/options')body=[{id:42,real_name:'项目负责人',username:'A001'},{id:43,real_name:'部门负责人',username:'A002'}]
  else if(path==='/api/product-lines/options')body={options:[{value:7,label:'产品线甲'}],label_map:{7:'产品线甲'}}
  else if(path==='/api/projects/archives/fields')body={items:names.map(field_key=>({field_key,label:field_key,visible:true,editable:field_key!=='customer_full_name',list_available:true,required:['archive_category','project_code','project_name','product_line_id','quantity','quantity_unit','manager_id','machine_model'].includes(field_key),required_when:['equipment_series','serial_no'].includes(field_key)?{field:'archive_category',values:[1]}:null,required_effective_at:'2026-10-14T10:00:00'}))}
  else if(path==='/api/dicts/code/archive_change_status')body={items:[{value:2,label:'待审批'},{value:3,label:'已通过'}],label_map:{2:'待审批',3:'已通过'}}
  else if(path.startsWith('/api/dicts/code/'))body={items:[{value:1,label:'主机'},{value:2,label:'辅机'},{value:7,label:'台'}],label_map:{1:'主机',2:'辅机',7:'台'}}
  else if(path==='/api/projects/archives/list')body={total:1,items:[row]}
  else if(path==='/api/projects/archive-changes/1/preview')body={mode:'approval',approver_id:43,approver_name:'部门负责人（A002）',expected_version:row.change_version,updates:route.request().postDataJSON().updates,differences:[{field_key:'project_name',field_label:'项目名称',before_display:'正式名称',after_display:'等待审批'}]}
  else if(path==='/api/projects/archive-changes/1/submit'){submitted=true;row.can_edit=false;row.pending_change_id=1;body={id:1,status:2,version:1,msg:'变更已提交审批'}}
  else if(path==='/api/projects/archive-changes/requests/1/decide'){
   if(failDecision)return route.fulfill({status:409,json:{detail:'测试版本冲突'}})
   status=3;row.project_name='等待审批';row.pending_change_id=null;body={id:1,status:3,version:2,opinion:route.request().postDataJSON().opinion}
  }
  else if(path==='/api/projects/archive-changes')body={total:submitted?1:0,items:submitted?[{id:1,archive_id:1,project_code:'GOV-001',status,version:status===2?1:2,author_name:'项目负责人',approver_name:'部门负责人',reason:'验收原因',differences:[{field_label:'项目名称',before_display:'正式名称',after_display:'等待审批'}],can_withdraw:status===2&&actor===42,can_approve:status===2&&actor===43}]:[]}
  if(['POST','PUT'].includes(method))writes.push({path,data:route.request().postDataJSON()})
  await route.fulfill({json:body})
 })
 await page.goto('http://127.0.0.1:5174/project/archive')
 await expect(page.getByRole('button',{name:'编辑',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'新增档案',exact:true}).click()
 const create=page.getByRole('dialog',{name:'新增项目档案',exact:true})
 await expect(create).toBeVisible()
 const labels=await create.locator('.pms-form-field__label').allTextContents()
 assert.deepEqual(labels.slice(0,11).map(label=>label.replace('*','').trim()),['档案类别','项目编号','项目名称','客户名称','产品线','数量','单位','负责人','机型','设备系列','序列号'])
 assert.equal(await create.locator('#archive-create-customer_full_name').count(),0)
 assert.equal(await create.locator('[id*="plan_start"],[id*="plan_end"]').count(),0)
 for(const size of [{width:1366,height:768},{width:1100,height:650}]){
  await page.setViewportSize(size)
  await expect.poll(async()=>{const box=await create.boundingBox();return box.x>=0&&box.x+box.width<=size.width&&box.y+box.height<=size.height}).toBe(true)
  const dimensions=await create.boundingBox()
  assert.ok(dimensions.x>=0&&dimensions.x+dimensions.width<=size.width&&dimensions.y+dimensions.height<=size.height)
  assert.equal(Math.round(dimensions.width),460)
  const heights=await create.locator('.pms-form-control').evaluateAll(items=>items.filter(item=>!item.querySelector('textarea')).map(item=>Math.round(item.getBoundingClientRect().height)))
  assert.ok(heights.every(height=>height===32),JSON.stringify(heights))
  await page.screenshot({path:`../outputs/archive-governance-20261014/create-${size.width}.png`})
 }
 await create.getByRole('button',{name:'取消',exact:true}).click()
 await page.getByRole('button',{name:'编辑',exact:true}).click()
 const drawer=page.getByRole('dialog',{name:'编辑项目档案',exact:true})
 await expect(drawer).toBeVisible()
 await drawer.getByRole('textbox',{name:'项目名称',exact:true}).fill('等待审批')
 await drawer.getByRole('button',{name:/提交变更/}).click()
 const confirm=page.getByRole('dialog',{name:'确认档案变更',exact:true})
 await expect(confirm).toContainText('部门负责人（A002）')
 await confirm.getByRole('button',{name:'提交审批',exact:true}).click()
 await expect(confirm).toContainText('请填写变更原因')
 assert.ok(!writes.some(write=>write.path.endsWith('/submit')))
 await confirm.getByRole('textbox',{name:'变更原因',exact:true}).fill('验收原因')
 await confirm.getByRole('button',{name:'提交审批',exact:true}).click()
 assert.ok(writes.some(write=>write.path.endsWith('/submit')&&write.data.expected_version==='a'.repeat(64)))
 assert.ok(!writes.some(write=>write.path==='/api/projects/archives/1'))
 await page.getByRole('button',{name:'变更审批',exact:true}).click()
 await expect(page.getByRole('gridcell',{name:'待审批',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'查看',exact:true}).click()
 const review=page.getByRole('dialog',{name:'档案变更审批',exact:true})
 await expect(review).toContainText('等待审批')
 await expect(review.getByRole('button',{name:'通过',exact:true})).toHaveCount(0)
 await review.getByRole('button',{name:'关闭',exact:true}).click()
 actor=43
 await page.reload()
 await page.getByRole('button',{name:'变更审批',exact:true}).click()
 await page.getByRole('button',{name:'查看',exact:true}).click()
 await review.getByRole('textbox',{name:'审批意见',exact:true}).fill('隔离验收结论')
 failDecision=true
 await review.getByRole('button',{name:'通过',exact:true}).click()
 await expect(review).toContainText('操作失败')
 await expect(review.getByRole('textbox',{name:'审批意见',exact:true})).toHaveValue('隔离验收结论')
 assert.equal(row.project_name,'正式名称')
 failDecision=false
 await review.getByRole('button',{name:'通过',exact:true}).click()
 await expect(page.getByRole('gridcell',{name:'已通过',exact:true})).toBeVisible()
 await expect(review).toContainText('审批意见：隔离验收结论')
 assert.equal(row.project_name,'等待审批')
 await page.screenshot({path:'../outputs/archive-governance-20261014/approval-verified.png'})
 assert.deepEqual(errors,[])
 console.log('Archive real page: approved layout, owner request, formal untouched, approval list passed')
}finally{await browser.close()}
