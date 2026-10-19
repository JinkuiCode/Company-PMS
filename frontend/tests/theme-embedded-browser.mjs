import {chromium,expect} from '@playwright/test'
import assert from 'node:assert/strict'
import {mkdir,writeFile} from 'node:fs/promises'
const base='http://127.0.0.1:5184',output=new URL('../../outputs/theme-application/',import.meta.url)
await mkdir(output,{recursive:true})
const browser=await chromium.launch({channel:'msedge',headless:true})
const page=await browser.newPage(),errors=[],network=[],checks=[]
page.setDefaultTimeout(15000)
page.on('pageerror',e=>errors.push(e.message))
page.on('request',request=>{const url=new URL(request.url());if(url.protocol.startsWith('http')&&(url.origin!==base||url.pathname.startsWith('/api/')))network.push(request.url())})
try{
  for(const [width,height] of [[1920,1080],[1366,768],[768,900],[390,844]]){
    await page.setViewportSize({width,height});await page.goto(base+'/application-pilot.html')
    const frame=page.frameLocator('iframe')
    await expect(frame.getByRole('button',{name:'查询',exact:true})).toBeEnabled({timeout:15000})
    await frame.getByRole('button',{name:'查询',exact:true}).click()
    await expect(frame.getByRole('progressbar').first()).toBeVisible()
    assert.ok(await frame.locator('html').evaluate(el=>el.scrollWidth<=innerWidth+1),`PMS iframe overflows at${width}`)
    for(const [id,name] of [['blue','办公蓝'],['teal','青绿'],['graphite','石墨']]){
      await frame.getByRole('button',{name:'切换外观',exact:true}).click();await frame.getByRole('menuitem',{name,exact:true}).click()
      await expect(frame.locator('html')).toHaveAttribute('data-pms-theme',id)
      assert.equal(Math.round(await frame.locator('.app-header').evaluate(el=>el.getBoundingClientRect().height)),44)
      assert.equal(Math.round(await frame.locator('.app-aside').evaluate(el=>el.getBoundingClientRect().width)),64)
      await frame.locator('.app-menu .el-sub-menu').filter({hasText:'报表中心'}).locator('.el-sub-menu__title').hover()
      await expect(frame.getByRole('menuitem',{name:'即时库存查询',exact:true}).filter({visible:true})).toBeVisible()
      await page.screenshot({path:new URL(`embedded-${width}-${id}.png`,output).pathname,fullPage:true,animations:'disabled'})
      await frame.locator('.header-title').hover()
    }
    checks.push(`${width}: actual app in OA-layout iframe, three themes,44px header,64px icon rail, no document overflow`)
  }
  assert.deepEqual(errors,[]);assert.deepEqual(network,[])
  await writeFile(new URL('embedded-result.json',output),JSON.stringify({passed:true,checks,errors,network,realOa:false},null,2))
  console.log(JSON.stringify({passed:true,checks},null,2))
}catch(error){await page.screenshot({path:new URL('embedded-failure.png',output).pathname,fullPage:true});console.error({errors,network});throw error}
finally{await browser.close()}
