import assert from 'node:assert/strict'
import {test} from 'node:test'
import {nextTick} from 'vue'
import {fixture} from './query-workspace-ownership.test.mjs'
import {readSchemes,schemeStorageKey,saveScheme} from '../src/query-system/workspace.ts'

const key=schemeStorageKey(1,'archive')
function add(f,name='B',isDefault=false){
  const a=readSchemes(f.storage,key)[0]
  saveScheme(f.storage,key,[],{...a,name,isDefault,preferences:{owner:name}},f.props.fields)
}
async function target(f,name){assert.equal(typeof f.state.selectEditor,'function','settings needs its own personal scheme selector');await f.state.selectEditor(name)}
async function remove(f){assert.equal(typeof f.state.deleteCurrent,'function','settings needs a confirmed personal scheme delete action');await f.state.deleteCurrent()}

test('editing another plan preserves its preferences and active conditions/results',async t=>{
  const f=fixture(t);add(f)
  f.props.snapshot=()=>({owner:'current-page',purchaseMaterialLayoutVersion:1})
  f.state.openSettings();await target(f,'B')
  const before=f.events.length,conditions=JSON.stringify(f.state.conditions.value)
  f.state.name.value='B-renamed';f.state.save();await nextTick()
  assert.equal(f.state.selected.value,'A-scheme')
  assert.equal(JSON.stringify(f.state.conditions.value),conditions)
  assert.deepEqual(f.events.slice(before),[])
  const saved=readSchemes(f.storage,key).find(s=>s.name==='B-renamed')
  assert.deepEqual(saved.preferences,{owner:'B'})
})

test('deleting current/default/last plan resets to system conditions without query',async t=>{
  const f=fixture(t);f.state.openSettings()
  const before=f.events.filter(e=>e[0]==='query').length
  await remove(f);await nextTick()
  assert.equal(f.state.selected.value,'')
  assert.equal(f.state.conditions.value[0].value,null)
  assert.equal(f.state.pendingQuery.value,true)
  assert.deepEqual(readSchemes(f.storage,key),[])
  assert.equal(f.events.filter(e=>e[0]==='query').length,before)
  assert.match(f.confirmations[0][0],/A-scheme/)
})

test('deleting a non-current ordinary plan leaves active draft and filters untouched',async t=>{
  const f=fixture(t);add(f);f.state.openSettings();await target(f,'B')
  const before=f.events.length,conditions=JSON.stringify(f.state.conditions.value)
  await remove(f)
  assert.equal(f.state.selected.value,'A-scheme')
  assert.equal(JSON.stringify(f.state.conditions.value),conditions)
  assert.deepEqual(f.events.slice(before),[])
})

test('deleting the personal default resets active selection even when another plan was active',async t=>{
  const f=fixture(t);add(f,'B',true);f.state.openSettings();await target(f,'B')
  await remove(f)
  assert.equal(f.state.selected.value,'')
  assert.equal(f.state.conditions.value[0].value,null)
  assert.equal(readSchemes(f.storage,key).some(s=>s.isDefault),false)
})

test('cancel deletion preserves plan and settings; system default cannot be deleted',async t=>{
  const f=fixture(t);f.state.openSettings();const before=f.storage.getItem(key)
  f.confirmResults.push(false);await remove(f)
  assert.equal(f.storage.getItem(key),before);assert.equal(f.state.opened.value,true)
  await target(f,'');await remove(f)
  assert.equal(f.storage.getItem(key),before)
})

test('unsaved switching and closing can be cancelled without losing input',async t=>{
  const f=fixture(t);add(f);f.state.openSettings();f.state.name.value='A-draft'
  f.confirmResults.push(false);await target(f,'B')
  assert.equal(f.state.originalName.value,'A-scheme');assert.equal(f.state.name.value,'A-draft')
  let closed=false;f.confirmResults.push(false)
  assert.equal(typeof f.state.beforeClose,'function')
  await f.state.beforeClose(()=>{closed=true})
  assert.equal(closed,false);assert.equal(f.state.name.value,'A-draft')
  f.confirmResults.push(true);await target(f,'B')
  assert.equal(f.state.originalName.value,'B')
})

test('failed writes and cross-tab conflicts preserve the editor draft',async t=>{
  const f=fixture(t);f.state.openSettings();const original=f.storage.getItem(key)
  f.state.name.value='A-draft';f.storage.fail=true;f.state.save()
  assert.equal(f.storage.getItem(key),original);assert.equal(f.state.opened.value,true);assert.equal(f.state.name.value,'A-draft')
  f.storage.fail=false
  const current=JSON.parse(original);current[0].definitions[0].value='other-tab';f.data.set(key,JSON.stringify(current))
  f.state.save()
  assert.match(f.state.configErrors.value.name,/其他|更新|变更|冲突/)
  assert.equal(f.state.name.value,'A-draft');assert.equal(f.state.opened.value,true)
})

test('identity switch during confirmation cannot delete the new or previous user scheme',async t=>{
  const f=fixture(t);f.state.openSettings();const before=[...f.data]
  let accept;f.confirmResults.push(()=>new Promise(resolve=>{accept=resolve}))
  const pending=remove(f);await nextTick();f.auth.user={id:2};await nextTick();accept();await pending
  assert.deepEqual([...f.data],before);assert.equal(f.state.opened.value,false)
})

test('leaving the page with unsaved settings can be cancelled and does not save implicitly',async t=>{
  const f=fixture(t);f.state.openSettings();f.state.name.value='unfinished'
  assert.equal(typeof f.leaveGuard,'function','shared settings needs a local unsaved route-leave guard')
  const original=f.storage.getItem(key)
  f.confirmResults.push(false);assert.equal(await f.leaveGuard(),false)
  assert.equal(f.state.name.value,'unfinished');assert.equal(f.storage.getItem(key),original)
  f.confirmResults.push(true);assert.equal(await f.leaveGuard(),true)
  assert.equal(f.storage.getItem(key),original)
})

test('only the latest scheme switch wins a shared unsaved confirmation',async t=>{
  const f=fixture(t);add(f,'B');add(f,'C');f.state.openSettings();f.state.name.value='draft'
  let accept;f.confirmResults.push(()=>new Promise(resolve=>{accept=resolve}))
  const first=target(f,'B'),last=target(f,'C');accept();await Promise.all([first,last])
  assert.equal(f.state.originalName.value,'C');assert.equal(f.state.name.value,'C')
})

test('temporary page conditions are copied only on explicit save of the current scheme',async t=>{
  const f=fixture(t);const original=f.storage.getItem(key)
  f.state.change([{id:1,field:'code',operator:'startsWith',value:'temporary',valueEnd:null}])
  f.state.openSettings()
  assert.equal(f.state.editDefinitions.value[0].value,'temporary')
  assert.equal(f.storage.getItem(key),original)
  f.state.save();await nextTick()
  assert.equal(readSchemes(f.storage,key)[0].definitions[0].value,'temporary')
})

test('corrupt storage blocks queries and cannot be overwritten by settings',async t=>{
  const f=fixture(t);f.data.set(key,'broken')
  f.state.openSettings();const before=f.events.filter(e=>e[0]==='query').length
  await f.state.query();f.state.name.value='repair';f.state.save()
  assert.match(f.state.storageError.value,/格式|读取/)
  assert.equal(f.state.storageWritable.value,false);assert.equal(f.data.get(key),'broken')
  assert.equal(f.events.filter(e=>e[0]==='query').length,before)
})

test('editing another E1 plan retains its layout marker, exact order and pin independently',async t=>{
  const f=fixture(t);add(f)
  const plans=readSchemes(f.storage,key),b=plans.find(s=>s.name==='B')
  b.preferences={purchaseMaterialLayoutVersion:1,visible:['material_code','material_name'],columns:[{colId:'material_code',pinned:'right',width:176},{colId:'material_name',pinned:'right',width:241}],pageSize:200}
  f.data.set(key,JSON.stringify(plans));f.props.snapshot=()=>({purchaseMaterialLayoutVersion:1,visible:['bill_no'],pageSize:50})
  f.state.openSettings();await target(f,'B');f.state.name.value='B-layout';f.state.save()
  assert.deepEqual(readSchemes(f.storage,key).find(s=>s.name==='B-layout').preferences,b.preferences)
})

test('an old user confirmation cannot discard the next user draft',async t=>{
  const f=fixture(t);f.state.openSettings();f.state.name.value='old draft'
  let oldAccept,newAccept;f.confirmResults.push(()=>new Promise(resolve=>{oldAccept=resolve}))
  const oldClose=f.state.requestClose()
  f.auth.user={id:2};await nextTick();f.state.openSettings();f.state.name.value='new draft'
  f.confirmResults.push(()=>new Promise(resolve=>{newAccept=resolve}))
  const newClose=f.state.requestClose()
  assert.equal(f.confirmations.length,2,'new owner requires a separate confirmation')
  oldAccept();await oldClose
  assert.equal(f.state.opened.value,true);assert.equal(f.state.name.value,'new draft')
  newAccept();await newClose;assert.equal(f.state.opened.value,false)
})

test('new owner storage errors cannot expose the previous owner scheme or condition',async t=>{
  const f=fixture(t);f.data.set(schemeStorageKey(2,'archive'),'broken')
  f.auth.user={id:2};await nextTick()
  assert.equal(f.state.selected.value,'');assert.equal(f.state.schemes.value.length,0)
  assert.equal(f.state.conditions.value[0]?.value??null,null)
  f.state.openSettings();assert.equal(f.state.originalName.value,'');assert.equal(f.state.name.value,'')
})

test('delete cleanup remains available when readiness temporarily changes',async t=>{
  const f=fixture(t);f.state.openSettings()
  let cancel;f.confirmResults.push(()=>new Promise((_,reject)=>{cancel=reject}))
  const pending=remove(f);f.props.ready=false;cancel('cancel');await pending
  assert.equal(f.state.deleting.value,false)
  f.props.ready=true;await nextTick()
  let closed=false;await f.state.beforeClose(()=>{closed=true})
  assert.equal(closed,true)
})

test('deleting the last ordinary personal plan clears temporary system-default conditions',async t=>{
  const f=fixture(t),plans=readSchemes(f.storage,key);plans[0].isDefault=false;f.data.set(key,JSON.stringify(plans))
  f.state.selected.value='';f.state.reset()
  f.state.change([{id:1,field:'code',operator:'equals',value:'temporary-system',valueEnd:null}])
  f.state.openSettings();await target(f,'A-scheme')
  const queries=f.events.filter(e=>e[0]==='query').length
  await remove(f)
  assert.equal(f.state.selected.value,'');assert.equal(f.state.conditions.value[0].value,null)
  assert.equal(f.state.pendingQuery.value,true);assert.equal(f.events.filter(e=>e[0]==='query').length,queries)
})
