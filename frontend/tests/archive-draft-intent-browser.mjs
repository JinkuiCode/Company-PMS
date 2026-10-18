import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
const out='../outputs/archive-draft-management-20261016/identity-browser'
fs.mkdirSync(out,{recursive:true})
const browser=await chromium.launch({channel:'msedge',headless:true})
try{
 const page=await browser.newPage({viewport:{width:1366,height:850}}),api=[],errors=[]
 const base='http://127.0.0.1:5174',rows=new Map();let writes=0
 const labels={project_code:'项目编号',project_name:'项目名称',archive_category:'档案类别',machine_model:'机型',quantity:'数量',quantity_unit:'单位',product_line_id:'产品线',manager_id:'负责人',equipment_series:'设备系列',serial_no:'序列号',contract_signed_date:'合同签订日期',contract_ship_date:'合同出货日期',address_province:'省份',address_city:'城市',address_detail:'详细地址'}
 const required=['project_code','project_name','archive_category','machine_model','quantity','quantity_unit','manager_id','product_line_id','contract_signed_date','contract_ship_date']
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-draft-intent-fixture'))
 await page.route('**/*',async r=>{
  const u=new URL(r.request().url()),p=u.pathname,m=r.request().method()
  if(u.origin!==base)return r.abort()
  if(!p.startsWith('/api/'))return r.continue()
  api.push(p);let data=[]
  if(p==='/api/auth/me')data={id:900000001,username:'fixture',real_name:'样稿用户',permissions:['project:archive:view','project:archive:add']}
  else if(p==='/api/users/options')data=[{id:900000001,real_name:'样稿用户'}]
  else if(p==='/api/product-lines/options'||p==='/api/product-lines/labels'||p==='/api/form-drafts/archive-create/product-lines')data={options:[{value:1,label:'8吋Bench'}],label_map:{1:'8吋Bench'}}
  else if(p==='/api/projects/archives/fields')data={items:Object.entries(labels).map(([field_key,label])=>({field_key,label,visible:true,editable:true,list_available:true,required:required.includes(field_key),...(['equipment_series','serial_no'].includes(field_key)?{governance_required:true,required_when:{field:'archive_category',values:[1]}}:{})}))}
  else if(p.startsWith('/api/dicts/code/')){const code=p.split('/').at(-1),items=code==='archive_category'?[{value:1,label:'主机'},{value:2,label:'AS类'}]:[{value:1,label:'样稿选项'}];data={items,all_items:items,label_map:Object.fromEntries(items.map(i=>[i.value,i.label]))}}
  else if(p==='/api/projects/archives/list')data={items:[],total:0}
  else if(p==='/api/form-drafts/archive-create'&&m==='GET')data={items:[...rows.values()].filter(i=>i.status==='active'),total:rows.size}
  else if(p==='/api/form-drafts/archive-create'&&m==='POST'){
   writes++;const b=r.request().postDataJSON();data={id:b.id,version:(rows.get(b.id)?.version||0)+1,status:'active',payload:b.payload,project_code:b.payload.project_code,project_name:b.payload.project_name,updated_at:'2026-10-16T15:10:00+08:00'};rows.set(b.id,data)
  }else if(p.startsWith('/api/form-drafts/archive-create/'))data=rows.get(p.split('/')[4])
  else if(m!=='GET')throw new Error('Unexpected mutation: '+m+' '+p)
  return r.fulfill({json:data})
 })
 page.on('pageerror',e=>errors.push(e.message));page.setDefaultTimeout(8000)
 await page.goto(base+'/project/archive')
 await page.addStyleTag({content:'*{animation:none!important;transition:none!important}'})
 await page.getByRole('button',{name:'新增档案',exact:true}).click()
 const form=page.getByRole('dialog',{name:'新增项目档案',exact:true})
 const stars=form.locator('.pms-form-field__required')
 const mark=label=>form.locator('.pms-form-field__label').filter({hasText:label}).locator('.pms-form-field__required')
 await expect(stars).toHaveCount(3)
 await expect(mark('项目编号')).toHaveCount(1);await expect(mark('项目名称')).toHaveCount(1);await expect(mark('数量')).toHaveCount(0)
 await expect(form.getByRole('button',{name:'正式保存',exact:true})).toBeVisible()
 await form.getByRole('textbox',{name:'项目编号',exact:true}).fill('INTENT-001')
 await form.getByRole('textbox',{name:'项目名称',exact:true}).fill('按保存操作显示必输')
 await expect(form).not.toContainText('请填写数量')
 await page.screenshot({path:out+'/draft-mode.jpg',animations:'disabled'})
 await form.getByRole('button',{name:'正式保存',exact:true}).click()
 await expect(mark('数量')).toHaveCount(1);await expect(form).toContainText('请填写数量')
 await expect(form).toContainText('请选择合同签订日期')
 await expect(page.locator(':focus')).toHaveAttribute('id','archive-create-archive_category')
 await form.locator('.pms-form-field').filter({hasText:'档案类别'}).locator('.el-select__wrapper').click()
 await page.getByRole('option',{name:'主机',exact:true}).click()
 await expect(mark('序列号')).toHaveCount(1)
 await page.screenshot({path:out+'/formal-mode.jpg',animations:'disabled'})
 await form.getByRole('button',{name:'减少数值',exact:true}).click()
 await expect(form.getByRole('spinbutton',{name:'数量',exact:true})).toHaveValue('-1')
 await expect(form).toContainText('数量只允许填写正整数')
 await form.getByRole('button',{name:'保存草稿',exact:true}).click()
 await expect(stars).toHaveCount(3)
 await expect(form).not.toContainText('请选择合同签订日期');await expect(form).toContainText('数量只允许填写正整数')
 await expect(page.getByText('草稿已保存',{exact:true})).toHaveCount(0)
 await page.screenshot({path:out+'/draft-format-error.jpg',animations:'disabled'})
 await form.getByRole('button',{name:'增加数值',exact:true}).click();await form.getByRole('button',{name:'增加数值',exact:true}).click()
 await expect(form.getByRole('spinbutton',{name:'数量',exact:true})).toHaveValue('1')
 await form.getByRole('button',{name:'保存草稿',exact:true}).click()
 await expect(page.getByText('草稿已保存',{exact:true})).toBeVisible()
 await expect(form).not.toContainText('数量只允许填写正整数');await expect(stars).toHaveCount(3)
 await form.getByRole('button',{name:'取消',exact:true}).click()
 await page.getByRole('button',{name:'我的草稿',exact:true}).click()
 await page.getByRole('dialog',{name:'我的草稿',exact:true}).getByRole('button',{name:'继续填写',exact:true}).click()
 await expect(stars).toHaveCount(3);await expect(form.getByRole('textbox',{name:'项目编号',exact:true})).toHaveValue('INTENT-001')
 await expect(form).not.toContainText('请选择合同签订日期')
 assert.equal(writes,1,'invalid local inputs must not reach draft save')
 await form.getByRole('button',{name:'正式保存',exact:true}).click()
 await expect(mark('数量')).toHaveCount(1)
 await form.getByRole('button',{name:'取消',exact:true}).click()
 await page.getByRole('button',{name:'新增档案',exact:true}).click()
 await expect(stars).toHaveCount(3)
 await expect(form.getByRole('textbox',{name:'项目编号',exact:true})).toHaveValue('')
 assert.deepEqual(errors,[])
 console.log('PASS draft stars=3; formal required markers/errors and conditional fields; switch back clears missing-only errors but preserves quantity format error; corrected draft saves/restores; actual route; all API responses synthetic; real writes=0')
}finally{await browser.close()}
