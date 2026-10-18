import assert from 'node:assert/strict'
import { test } from 'node:test'
import { reactive } from 'vue'
import { existsSync } from 'node:fs'
const target = new URL('../src/form-system/useFormSession.ts', import.meta.url)
const mod = existsSync(target) ? await import(target.href) : {}
function setup(value = { name: '原名', nested: { amount: 1 } }) {
  assert.equal(typeof mod.useFormSession, 'function', '共享表单会话控制器必须存在')
  const draft = reactive(value)
  return { draft, session: mod.useFormSession({ draft, isConflict: e => e?.status === 409 }) }
}
function deferred() { let resolve, reject; const promise = new Promise((ok, no) => { resolve = ok; reject = no }); return { promise, resolve, reject } }

test('原值深拷贝，修改、还原和重新建立基线', () => {
  const {draft,session:s}=setup()
  assert.equal(s.dirty.value,false)
  draft.nested.amount=2
  assert.equal(s.original.value.nested.amount,1)
  assert.equal(s.dirty.value,true)
  draft.extra='新字段'; assert.equal(s.restore(),true)
  assert.equal(draft.nested.amount,1);assert.equal('extra' in draft,false)
  draft.name='新名';assert.equal(s.capture(),true)
  assert.equal(s.dirty.value,false);assert.equal(s.original.value.name,'新名')
})
test('从验证开始锁定，快速重复提交只调用一次验证与保存',async()=>{
  const {session:s}=setup();const gate=deferred();let validations=0,writes=0
  const operation={validate:async()=>{validations++;return gate.promise},save:async()=>++writes}
  const first=s.submit(operation)
  assert.equal(s.phase.value,'validating');assert.equal(s.busy.value,true)
  assert.deepEqual(await s.submit(operation),{status:'busy'})
  gate.resolve(true)
  assert.deepEqual(await first,{status:'success',value:1})
  assert.equal(validations,1);assert.equal(writes,1);assert.equal(s.busy.value,false)
})
test('校验失败不提交、保留草稿，校验异常也释放互斥',async()=>{
  const {draft,session:s}=setup();draft.name='草稿';let writes=0
  assert.deepEqual(await s.submit({validate:async()=>false,save:async()=>writes++}),{status:'invalid'})
  assert.equal(writes,0);assert.equal(draft.name,'草稿');assert.equal(s.dirty.value,true)
  const error=new Error('校验依赖加载失败')
  const result=await s.submit({validate:async()=>{throw error},save:async()=>writes++})
  assert.equal(result.status,'failed');assert.equal(result.error,error);assert.equal(s.busy.value,false)
})
test('失败与冲突不确认原值，修正后可重试',async()=>{
  const {draft,session:s}=setup();draft.name='改名'
  for(const error of [new Error('断网'),{status:409,message:'已被其他人修改'}]){
    const result=await s.submit({validate:async()=>true,save:async()=>{throw error}})
    assert.equal(result.status,'failed');assert.equal(result.error,error)
    assert.equal(s.phase.value,error.status===409?'conflict':'error')
    assert.equal(s.original.value.name,'原名');assert.equal(draft.name,'改名');assert.equal(s.dirty.value,true)
  }
  assert.equal((await s.submit({validate:async()=>true,save:async()=>42})).status,'success')
  assert.equal(s.error.value,null);assert.equal(s.phase.value,'idle');assert.equal(s.dirty.value,false)
})
test('保存使用独立快照，提交后新草稿不能误标为已保存',async()=>{
  const {draft,session:s}=setup();draft.name='提交值';const gate=deferred();let received
  const pending=s.submit({validate:async()=>true,save:async snapshot=>{received=snapshot;return gate.promise}})
  await Promise.resolve();assert.equal(received.name,'提交值')
  draft.name='较新的草稿';assert.equal(received.name,'提交值')
  gate.resolve('ok');await pending
  assert.equal(s.original.value.name,'提交值');assert.equal(draft.name,'较新的草稿');assert.equal(s.dirty.value,true)
})
test('验证或保存期间不得建立新基线、还原或关闭',async()=>{
  const {draft,session:s}=setup();draft.name='草稿';const validation=deferred(),save=deferred();let confirms=0
  const pending=s.submit({validate:()=>validation.promise,save:()=>save.promise})
  for(const stage of ['validating','saving']){
    if(stage==='saving'){validation.resolve(true);await Promise.resolve();await Promise.resolve()}
    assert.equal(s.capture(),false);assert.equal(s.restore(),false)
    assert.equal(await s.requestClose(async()=>{confirms++;return true}),false)
  }
  assert.equal(confirms,0);assert.equal(draft.name,'草稿');save.resolve(null);await pending
})
test('关闭确认互斥，取消保留草稿，确认后才允许关闭',async()=>{
  const {draft,session:s}=setup();draft.name='草稿';const gate=deferred();let confirms=0,writes=0
  const closing=s.requestClose(async()=>{confirms++;return gate.promise})
  assert.equal(await s.requestClose(async()=>{confirms++;return true}),false)
  assert.deepEqual(await s.submit({validate:async()=>true,save:async()=>writes++}),{status:'busy'})
  gate.resolve(false);assert.equal(await closing,false);assert.equal(confirms,1);assert.equal(writes,0)
  assert.equal(draft.name,'草稿');assert.equal(s.dirty.value,true)
  assert.equal(await s.requestClose(async()=>true),true)
  assert.equal(draft.name,'草稿','控制器不擅自删除业务草稿，由调用方关闭后处理')
})
test('无修改可直接关闭；确认抛错后仍可再次操作',async()=>{
  const {draft,session:s}=setup();let prompts=0
  assert.equal(await s.requestClose(async()=>{prompts++;return false}),true);assert.equal(prompts,0)
  draft.name='草稿'
  assert.equal(await s.requestClose(async()=>{throw new Error('取消')}),false)
  assert.equal(await s.requestClose(async()=>true),true)
})

test('异步字段错误定位完成前持续锁定，不把旧错误写到新一轮草稿',async()=>{
 const {session:s}=setup(),gate=deferred();let presenting=false
 const pending=s.submit({validate:async()=>true,save:async()=>{throw new Error('422')},onError:async()=>{presenting=true;await gate.promise}})
 await Promise.resolve();await Promise.resolve();await Promise.resolve()
 assert.equal(presenting,true);assert.equal(s.busy.value,true)
 assert.deepEqual(await s.submit({validate:async()=>true,save:async()=>42}),{status:'busy'})
 assert.equal(await s.requestClose(async()=>true),false)
 gate.resolve();assert.equal((await pending).status,'failed');assert.equal(s.busy.value,false)
})
