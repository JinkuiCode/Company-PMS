import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
import { execFileSync } from 'node:child_process'
import { resolve } from 'node:path'
const root=resolve(import.meta.dirname,'../..')
const metadata=JSON.parse(execFileSync('/Users/jin/.cache/codex-runtimes/codex-primary-runtime/dependencies/python/bin/python3',['-c','import json; from app.services.purchase_fields import *; from app.services.report_filters import filter_fields; print(json.dumps(dict(fields=report_fields(),overview_fields=overview_fields(),filter_fields=filter_fields("purchase"),progress_labels=PROGRESS_LABELS,document_status_labels=DOCUMENT_STATUSES,organizations=[dict(value=100,label="8吋Bench"),dict(value=200,label="Single")],start_date="2026-01-01")))'],{cwd:resolve(root,'backend'),env:{...process.env,PYTHONPATH:resolve(root,'backend/.venv-deps312')},encoding:'utf8'}))
const browser=await chromium.launch({channel:'msedge',headless:true})
const page=await browser.newPage({viewport:{width:1440,height:900}})
let releaseOld, releaseValidation, holdValidation=false, validationStarted=false, oldStarted=false, businessQueries=0
const requests=[], errors=[]
page.on('pageerror',error=>errors.push(error.message))
await page.addInitScript(()=>localStorage.setItem('access_token','fixture-token'))
await page.addInitScript(()=>localStorage.setItem('pms:purchase-report:v1:991',JSON.stringify({plans:[
  ...[{name:'失效项目限定',organization_id:100,project_code:'P-MISSING'},{name:'撤权组织限定',organization_id:999,project_code:'P-BENCH'}].map(p=>({name:p.name,filters:{keyword:'',project_code:'',supplier:'',progress:'',organization_ids:[]},dates:[],conditions:[],pageSize:50,columns:[],visible:['product_line_name','project_code','project_name'],sort:{sort:'date',direction:'desc'},scope:{organization_id:p.organization_id,project_code:p.project_code,product_line_name:'历史产品线'}}))
]})))
await page.route('**/api/**',async route=>{
  const url=new URL(route.request().url()),path=url.pathname
  if(!path.startsWith('/api/')) return route.continue()
  if(path==='/api/auth/me') return route.fulfill({json:{id:991,username:'fixture',real_name:'测试',permissions:['report:purchase:view'],role_codes:[],data_scope:1}})
  if(path==='/api/my-menus') return route.fulfill({json:[{id:4,menu_name:'报表中心',menu_type:'M',icon:'DataAnalysis',children:[{id:41,menu_name:'采购进度查询',path:'/reports/purchase-progress',icon:'Document'}]}]})
  if(path.endsWith('/metadata')) return route.fulfill({json:metadata})
  if(path.endsWith('/options')) {
    requests.push({ids:url.searchParams.getAll('organization_ids'),keyword:url.searchParams.get('keyword'),code:url.searchParams.get('project_code')})
    if(url.searchParams.get('field')!=='project') return route.fulfill({json:{items:[],has_more:false}})
    if(url.searchParams.get('keyword')==='slow') {oldStarted=true;await new Promise(resolve=>{releaseOld=resolve})}
    const ids=url.searchParams.getAll('organization_ids')
    const values=ids.includes('100')?['P-COMMON','P-BENCH']:ids.includes('200')?['P-COMMON','P-SINGLE']:['P-COMMON','P-BENCH','P-SINGLE']
    const exact=url.searchParams.get('project_code')
    if(exact&&holdValidation) {validationStarted=true;await new Promise(resolve=>{releaseValidation=resolve})}
    return route.fulfill({json:{items:values.filter(v=>!exact||v===exact).map(value=>({value,label:value})),has_more:false}})
  }
  if(path==='/api/reports/purchase/overview'||path==='/api/reports/purchase') {businessQueries++;return route.fulfill({json:{items:[],total:0,total_lines:0,complete_lines:0,review_lines:0,queried_at:'2026-10-09T06:00:00Z'}})}
  return route.fulfill({json:[]})
})
async function chooseProduct(surface,name){
  await surface.locator('.pms-form-control').filter({has:page.getByRole('combobox',{name:'产品线',exact:true})}).locator('.el-select__wrapper').click()
  await page.getByRole('option',{name,exact:true}).click()
  await page.keyboard.press('Escape')
}
async function chooseProject(surface,name){
  await surface.locator('.pms-form-control').filter({has:page.getByRole('combobox',{name:'项目编码筛选',exact:true})}).locator('.el-select__wrapper').click()
  await page.getByRole('option',{name,exact:true}).click()
}
try{
  await page.goto('http://127.0.0.1:5174/reports/purchase-progress')
  const overview=page.locator('.purchase-overview-page')
  await chooseProduct(overview,'8吋Bench')
  await chooseProject(overview,'P-BENCH')
  assert.deepEqual(requests.at(-1).ids,['100'],'项目候选必须带所选产品线')
  await overview.getByRole('button',{name:'保存查询方案',exact:true}).click()
  await page.getByRole('textbox',{name:'方案名称',exact:true}).fill('产品线项目组合')
  await page.getByRole('button',{name:'保存',exact:true}).filter({visible:true}).click()
  const project=overview.getByRole('combobox',{name:'项目编码筛选',exact:true})
  await project.fill('slow')
  await expect.poll(()=>oldStarted).toBe(true)
  await chooseProduct(overview,'8吋Bench')
  await chooseProduct(overview,'Single')
  await expect(project).toHaveValue('')
  await chooseProject(overview,'P-SINGLE')
  releaseOld()
  await expect(project).toHaveValue('')
  await overview.locator('.pms-report-plans .el-select__wrapper').hover()
  await overview.locator('.pms-report-plans .el-select__clear').click()
  holdValidation=true
  await overview.locator('.pms-report-plans .el-select__wrapper').click()
  await page.getByRole('option',{name:'产品线项目组合',exact:true}).click()
  await expect.poll(()=>requests.some(r=>r.code==='P-BENCH'&&r.ids.join()==='100')).toBe(true)
  await expect.poll(()=>validationStarted).toBe(true)
  await overview.locator('.pms-form-control').filter({has:page.getByRole('combobox',{name:'项目编码筛选',exact:true})}).locator('.el-select__wrapper').click()
  await expect.poll(()=>requests.at(-1).code).toBe('')
  releaseValidation();holdValidation=false
  await page.keyboard.press('Escape')
  await expect(overview.getByRole('button',{name:'查询',exact:true})).toBeEnabled()
  await expect(overview.locator('.pms-report-query-fields')).toContainText('P-BENCH')
  assert.equal(businessQueries,0,'联动和方案恢复不得自动查询报表')
  await page.getByRole('button',{name:'明细进度',exact:true}).filter({visible:true}).click()
  const detail=page.locator('.purchase-detail-view')
  await chooseProduct(detail,'Single')
  await chooseProject(detail,'P-SINGLE')
  assert.deepEqual(requests.at(-1).ids,['200'],'明细使用同一联动规则')
  await detail.locator('.pms-report-query-plan-select .el-select__wrapper').click()
  await page.getByRole('option',{name:'失效项目限定',exact:true}).click()
  await expect.poll(()=>requests.some(r=>r.code==='P-MISSING'&&r.ids.join()==='100')).toBe(true)
  await expect(detail.getByRole('button',{name:'查询',exact:true})).toBeDisabled()
  await detail.locator('.pms-report-query-plan-select .el-select__wrapper').click()
  await page.getByRole('option',{name:'撤权组织限定',exact:true}).click()
  await expect(page.getByText('查询方案包含不可选产品线，请重新配置方案',{exact:true})).toBeVisible()
  assert.equal(businessQueries,0)
  assert.deepEqual(errors,[])
  console.log('PASS product-line/project candidates, exact plan restoration, stale response rejection, no automatic report reads')
}finally{releaseOld?.();releaseValidation?.();await browser.close()}
