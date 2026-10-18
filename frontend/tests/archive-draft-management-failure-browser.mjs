import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
const browser=await chromium.launch({channel:'msedge',headless:true})
try{
 const page=await browser.newPage({viewport:{width:1440,height:900}}),errors=[]
 const base='http://127.0.0.1:5174',api='/api/archive-draft-management',id='00000000-0000-4000-8000-000000000001'
 const row={id,project_code:'UNKNOWN-001',project_name:'删除待核对草稿',creator_name:'测试人员',creator_enabled:true,product_line_name:'8吋Bench',product_line_id:1,status:'active',version:1,updated_at:'2026-10-16T16:40:00+08:00'}
 const other={...row,id:'00000000-0000-4000-8000-000000000002',project_code:'UNKNOWN-002'}
 let loadFails=true,deleted=false,reads=0,deletes=0
 await page.addInitScript(()=>localStorage.setItem('access_token','isolated-draft-failure-fixture'))
 page.on('pageerror',e=>errors.push(e.message))
 await page.route('**/*',route=>{
  const req=route.request(),u=new URL(req.url()),p=u.pathname,m=req.method()
  if(u.origin!==base)return route.abort()
  if(!p.startsWith('/api/'))return route.continue()
  const fulfill=(data,status=200)=>route.fulfill({status,json:data})
  if(p==='/api/auth/me')return fulfill({id:900000002,real_name:'验收用户',permissions:['project:archive:view','project:archive:draft:manage']})
  if(p===api){reads++;return loadFails?fulfill({detail:'暂时失败'},500):fulfill({items:deleted?[other]:[row,other],total:deleted?1:2})}
  if(p===api+'/'+id&&m==='DELETE'){deletes++;deleted=true;return route.abort('failed')}
  if(p===api+'/'+id)return fulfill({...row,fields:[{key:'project_code',label:'项目编号',display:row.project_code}],warnings:[]})
  if(m!=='GET')throw Error('Unexpected mutation '+p)
  return fulfill([])
 })
 await page.goto(base+'/project/archive-drafts')
 await page.addStyleTag({content:'*{transition:none!important;animation:none!important}'})
 await expect(page.getByText('草稿加载失败',{exact:false})).toBeVisible()
 loadFails=false;await page.getByRole('button',{name:'重试',exact:true}).click()
 const record=page.getByRole('row').filter({hasText:'UNKNOWN-001'})
 await expect(record).toBeVisible()
 const before=reads
 await record.getByRole('button',{name:'删除',exact:true}).click()
 await page.getByRole('dialog',{name:'删除草稿',exact:true}).getByRole('button',{name:'确认删除',exact:true}).click()
 await expect(page.getByRole('alert').filter({hasText:'删除结果暂未确认'})).toBeVisible()
 await expect(record.getByRole('button',{name:'删除',exact:true})).toBeDisabled()
 await expect(page.getByRole('row').filter({hasText:'UNKNOWN-002'}).getByRole('button',{name:'删除',exact:true})).toBeDisabled()
 assert.equal(deletes,1);assert.equal(reads,before,'unknown result must not trigger automatic retry/reload')
 await record.getByRole('button',{name:'查看',exact:true}).click()
 const detail=page.getByRole('dialog',{name:'草稿详情',exact:true})
 await expect(detail).toContainText('删除结果暂未确认')
 await expect(detail.getByRole('button',{name:'删除',exact:true})).toBeDisabled()
 await detail.getByRole('button',{name:'关闭此对话框',exact:true}).click()
 await expect(detail).toBeHidden()
 await page.getByRole('button',{name:'查询',exact:true}).click()
 await expect(record).toHaveCount(0)
 await expect(page.getByText('共 1 条',{exact:true})).toBeVisible()
 assert.equal(deletes,1);assert.deepEqual(errors,[])
 console.log('PASS management failure states: load retry, unknown delete remains disabled and explained in detail, explicit query reconciles, no automatic mutation retry; synthetic API only')
}finally{await browser.close()}
