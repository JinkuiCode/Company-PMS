import {createServer} from 'vite'
import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import {mkdir,writeFile} from 'node:fs/promises'
import {fixtureResponse} from './fixtures/theme-application-api.mjs'
const server=await createServer({server:{host:'127.0.0.1',port:0}})
const output=new URL('../../outputs/theme-application/',import.meta.url),errors=[],unknown=[],checks=[]
await mkdir(output,{recursive:true})
let browser
try{
  await server.listen()
  const base=`http://127.0.0.1:${server.httpServer.address().port}`
  browser=await chromium.launch({channel:'msedge',headless:true})
  const context=await browser.newContext({viewport:{width:1440,height:900}})
  await context.addInitScript(()=>localStorage.setItem('access_token','isolated-theme-test'))
  await context.route('**/api/**',route=>{
    const request=route.request(),url=new URL(request.url())
    if(!url.pathname.startsWith('/api/'))return route.continue()
    try{return route.fulfill({json:fixtureResponse(url.pathname.slice(4),url.searchParams,request.method())})}
    catch(error){unknown.push(String(error));return route.fulfill({status:501,json:{detail:String(error)}})}
  })
  const page=await context.newPage()
  page.on('pageerror',error=>errors.push(error.message))
  await page.goto(base+'/dashboard')
  await expect(page.locator('.dashboard canvas')).toHaveCount(2)
  for(const [id,name,rgb] of [['blue','办公蓝',[37,99,235]],['teal','青绿',[15,118,110]],['graphite','石墨',[39,39,42]]]){
    await page.getByRole('button',{name:'切换外观',exact:true}).click()
    await page.getByRole('menuitem',{name,exact:true}).click()
    await expect.poll(()=>page.locator('.dashboard canvas').evaluateAll((canvases,rgb)=>canvases.every(canvas=>{
      const pixels=canvas.getContext('2d').getImageData(0,0,canvas.width,canvas.height).data
      let matches=0
      for(let i=0;i<pixels.length;i+=4)if(pixels[i]===rgb[0]&&pixels[i+1]===rgb[1]&&pixels[i+2]===rgb[2]&&pixels[i+3]>200)matches++
      return matches>50
    }),rgb),{timeout:10000}).toBe(true)
    await page.screenshot({path:new URL('dashboard-canvas-'+id+'.png',output).pathname,animations:'disabled'})
  }
  checks.push('both actual dashboard canvases contain the active theme color after each switch; not blank')
  await page.goto(base+'/403')
  await expect(page.locator('.app-header')).toContainText('无权访问')
  await expect(page.locator('html')).toHaveAttribute('data-pms-theme','graphite')
  await page.screenshot({path:new URL('forbidden-graphite.png',output).pathname,animations:'disabled'})
  await page.goto(base+'/admin/token')
  await expect(page.getByRole('heading',{name:'OA 单点登录配置工具',exact:true})).toBeVisible()
  await expect(page.locator('.guide-card')).toHaveCSS('border-left-color','rgb(8, 126, 101)')
  await expect(page.locator('html')).toHaveAttribute('data-pms-theme','graphite')
  await page.screenshot({path:new URL('token-tool-graphite.png',output).pathname,animations:'disabled'})
  checks.push('forbidden and token-tool pages inherit the shared theme without submitting any action')
  const anonymous=await browser.newContext({viewport:{width:1366,height:768}})
  const login=await anonymous.newPage()
  login.on('pageerror',error=>errors.push(error.message))
  const anonymousApi=[]
  await anonymous.route('**/api/**',route=>{
    const url=new URL(route.request().url())
    if(!url.pathname.startsWith('/api/'))return route.continue()
    anonymousApi.push(url.href);return route.abort()
  })
  await login.goto(base+'/login')
  for(const id of ['blue','teal','graphite']){
    await login.evaluate(id=>localStorage.setItem(`pms:theme:public:v1:${encodeURIComponent(location.origin)}`,id),id)
    await login.reload()
    await expect(login.locator('html')).toHaveAttribute('data-pms-theme',id)
    await expect(login.getByRole('button',{name:'登录',exact:true})).toBeVisible()
    await login.screenshot({path:new URL('login-'+id+'.png',output).pathname,animations:'disabled'})
  }
  assert.deepEqual(anonymousApi,[])
  checks.push('actual login renders all three appearance hints without credentials or authentication requests')
  assert.deepEqual(errors,[]);assert.deepEqual(unknown,[])
  await writeFile(new URL('secondary-pages-result.json',output),JSON.stringify({passed:true,checks,errors,unknown,realBackend:false},null,2))
  console.log(JSON.stringify({passed:true,checks},null,2))
}finally{await browser?.close();await server.close()}
