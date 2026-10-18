import assert from 'node:assert/strict'
import {test} from 'node:test'
import {existsSync} from 'node:fs'
const url=new URL('../src/composables/usePageLoad.ts',import.meta.url)
const mod=existsSync(url)?await import(url.href):{}
function setup(){assert.equal(typeof mod.usePageLoad,'function','统一页面数据状态控制器必须存在');return mod.usePageLoad()}
test('初始待查询，成功区分空结果和数据',()=>{
 const s=setup();assert.equal(s.phase.value,'idle');assert.equal(s.hasQueried.value,false)
 const ticket=s.begin();assert.equal(s.phase.value,'loading');assert.equal(s.loading.value,true)
 assert.equal(s.succeed(ticket,true),true);assert.equal(s.phase.value,'empty');assert.equal(s.hasQueried.value,true)
 s.succeed(s.begin(),false);assert.equal(s.phase.value,'ready');assert.equal(s.loading.value,false)
})
test('失败保留原因，重试清理旧错误',()=>{
 const s=setup(),error=new Error('加载失败'),ticket=s.begin()
 assert.equal(s.fail(ticket,error),true);assert.equal(s.failed.value,true);assert.equal(s.error.value,error);assert.equal(s.loading.value,false)
 const retry=s.begin();assert.equal(s.failed.value,false);assert.equal(s.error.value,null)
 s.succeed(retry);assert.equal(s.phase.value,'ready')
})
test('旧成功和旧错误不能覆盖新请求状态',()=>{
 const s=setup(),first=s.begin(),second=s.begin()
 assert.equal(s.isCurrent(first),false);assert.equal(s.isCurrent(second),true)
 assert.equal(s.succeed(first),false);assert.equal(s.fail(first,new Error('旧错误')),false)
 assert.equal(s.loading.value,true);s.succeed(second)
 assert.equal(s.fail(first,new Error('迟到旧错误')),false);assert.equal(s.phase.value,'ready')
})
test('排序防抖等待阶段立即使旧响应失效',()=>{
 const s=setup(),first=s.begin();s.invalidate(true)
 assert.equal(s.loading.value,true);assert.equal(s.succeed(first),false)
 const next=s.begin();s.succeed(next,true);assert.equal(s.phase.value,'empty')
})
test('离页立即废弃请求，重新进入的控制器独立',()=>{
 const old=setup(),ticket=old.begin();old.invalidate()
 assert.equal(old.isCurrent(ticket),false);assert.equal(old.succeed(ticket),false);assert.equal(old.phase.value,'idle')
 const current=setup(),id=current.begin();assert.equal(current.isCurrent(id),true);assert.equal(old.isCurrent(id),false)
})
