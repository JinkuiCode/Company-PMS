import {createServer} from 'vite'
import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import {mkdir,writeFile} from 'node:fs/promises'
const server=await createServer({server:{host:'127.0.0.1',port:0}})
let browser
try{
  await server.listen()
  const base=`http://127.0.0.1:${server.httpServer.address().port}`
  browser=await chromium.launch({channel:'msedge',headless:true})
  const page=await browser.newPage()
  const errors=[],api=[]
  page.on('pageerror',error=>errors.push(error.message))
  await page.addInitScript(()=>{
    localStorage.setItem(`pms:theme:public:v1:${encodeURIComponent(location.origin)}`,'teal')
    const read=Storage.prototype.getItem
    Storage.prototype.getItem=function(key){if(key==='access_token')throw Error('Credential storage is unavailable');return read.call(this,key)}
  })
  await page.route('**/api/**',route=>{
    if(!new URL(route.request().url()).pathname.startsWith('/api/'))return route.continue()
    api.push(route.request().url());return route.fulfill({status:501,json:{detail:'No business session in public guide test'}})
  })
  await page.goto(base+'/page-guide/purchase')
  try{await expect(page.locator('.pms-guide-page')).toBeVisible({timeout:8000})}catch(error){console.error({errors,api});throw error}
  await expect(page.locator('html')).toHaveAttribute('data-pms-theme','teal')
  assert.deepEqual(errors,[]);assert.deepEqual(api,[])
  const output=new URL('../../outputs/theme-application/',import.meta.url);await mkdir(output,{recursive:true})
  await writeFile(new URL('public-guide-credential-guard.json',output),JSON.stringify({passed:true,errors,api,credentialStorageUnavailable:true},null,2))
  console.log('PASS: public guide renders with inherited appearance and unavailable credential storage')
}finally{await browser?.close();await server.close()}
