import { chromium, expect } from '@playwright/test'
import assert from 'node:assert/strict'
const browser=await chromium.launch({headless:true,channel:'chrome'})
try {
 const page=await browser.newPage({viewport:{width:1360,height:900}})
 const errors=[];page.on('pageerror',e=>errors.push(e.message))
 await page.addInitScript(()=>{
  localStorage.setItem('access_token','local-test-only')
  localStorage.setItem('pms_project_archive_list_columns_v2:1',JSON.stringify({selected_column_keys:['customer'],columnState:[{colId:'project_name',sort:'asc',sortIndex:0},{colId:'project_code',width:245}]}))
 })
 const rows=Array.from({length:121},(_,i)=>({id:i+1,project_code:`A-${String(121-i).padStart(4,'0')}`,project_name:`Name-${i}`,archive_category:i<80?1:i<110?2:null,is_enabled:1,data_origin:'offline_initial',erp_sync_policy:'manual',can_delete:false}))
 const requests=[]
 await page.route('**/api/**',async route=>{
  const url=new URL(route.request().url());if(!url.pathname.startsWith('/api/'))return route.continue();let body=[]
  if(url.pathname==='/api/auth/me')body={id:1,username:'test',real_name:'测试',permissions:['project:archive:view']}
  else if(url.pathname==='/api/auth/product-categories')body={unrestricted:true}
  else if(url.pathname==='/api/product-lines/options')body={options:[],label_map:{}}
  else if(url.pathname.includes('/dicts/code/'))body=url.pathname.endsWith('/archive_category')?{items:process.env.PMS_DISABLED_MAIN?[{value:'2',label:'辅机'}]:[{value:'1',label:'主机'},{value:'2',label:'辅机'}],all_items:[{value:'1',label:'主机'},{value:'2',label:'辅机'}],label_map:{1:'主机',2:'辅机'}}:{items:[],label_map:{}}
  else if(url.pathname==='/api/projects/archives/fields')body={items:process.env.PMS_HIDDEN_CATEGORY?[{field_key:'archive_category',visible:false}]:[]}
  else if(url.pathname==='/api/projects/archives/list'){
   const params=Object.fromEntries(url.searchParams);requests.push(params)
   const filters=JSON.parse(params.filters||'[]');let selected=[...rows]
   for(const f of filters){if(f.field==='archive_category'&&f.operator==='in')selected=selected.filter(a=>f.value.includes(a.archive_category))}
   const sort=JSON.parse(params.sort||'[]')[0]||{colId:'project_code',sort:'desc'}
   selected.sort((a,b)=>String(a[sort.colId]).localeCompare(String(b[sort.colId]))*(sort.sort==='desc'?-1:1))
   const offset=(Number(params.page)-1)*Number(params.page_size)
   body={total:selected.length,items:selected.slice(offset,offset+Number(params.page_size))}
  }
  await route.fulfill({json:body})
 })
 await page.goto(process.env.PMS_BROWSER_URL||'http://127.0.0.1:5181/project/archive')
 const category=page.getByRole('combobox',{name:'档案类别',exact:true})
 if(process.env.PMS_HIDDEN_CATEGORY){
  await expect(category).toHaveCount(0)
  await expect(page.getByText('共 121 条',{exact:true})).toBeVisible()
  assert.equal(JSON.parse(requests.at(-1).filters).some(f=>f.field==='archive_category'),false)
  assert.deepEqual(errors,[])
  console.log('archive hidden category browser passed: no invisible category filter')
 }else{
 await expect(category).toBeVisible()
 await expect(page.getByText('共 80 条',{exact:true})).toBeVisible(); assert.equal(Math.round(await page.locator('.ag-header-cell[col-id="project_code"]').evaluate(e=>e.getBoundingClientRect().width)),245,'Saved width must be preserved')
 assert.deepEqual(JSON.parse(requests.at(-1).filters).find(f=>f.field==='archive_category').value,[1])
 assert.deepEqual(JSON.parse(requests.at(-1).sort),[{colId:'project_code',sort:'desc'}],'Old name sort must not override approved initial code sort')
 await expect(page.getByRole('gridcell',{name:'A-0121',exact:true})).toBeVisible()
 await page.getByRole('button',{name:'2',exact:true}).click()
 await expect(page.getByRole('gridcell',{name:'A-0071',exact:true})).toBeVisible()
 assert.equal(requests.at(-1).page,'2')
 await page.locator('.archive-base-filter--archive-category .el-select__wrapper').click();await page.getByRole('option',{name:'辅机',exact:true}).click()
 await expect(page.getByText('共 110 条',{exact:true})).toBeVisible()
 assert.equal(requests.at(-1).page,'1')
 assert.deepEqual(JSON.parse(requests.at(-1).filters).find(f=>f.field==='archive_category').value,[1,2])
 await category.press('Escape')
 await page.locator('.archive-base-filter--archive-category .el-select__wrapper').click();await page.getByRole('option',{name:'主机',exact:true}).click()
 await expect(page.getByText('共 30 条',{exact:true})).toBeVisible()
 assert.deepEqual(JSON.parse(requests.at(-1).filters).find(f=>f.field==='archive_category').value,[2])
 await page.getByRole('option',{name:'辅机',exact:true}).click()
 await expect(page.getByText('共 121 条',{exact:true})).toBeVisible()
 assert.equal(JSON.parse(requests.at(-1).filters).some(f=>f.field==='archive_category'),false)
 await category.press('Escape')
 await page.getByRole('button',{name:'2',exact:true}).click()
 await expect(page.getByRole('gridcell',{name:'A-0071',exact:true})).toBeVisible()
 assert.deepEqual(errors,[])
 await page.screenshot({path:process.env.PMS_BROWSER_PROOF||'/Users/jin/Code/PMS/.runtime/archive-import-20261009/archive-default-query-local.png',fullPage:true})
 console.log('archive default query browser passed: default main, multi OR, clear all, reset page, saved sort, cross-page code DESC')
}
}finally{await browser.close()}
