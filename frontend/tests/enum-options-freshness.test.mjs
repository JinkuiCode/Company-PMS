import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { reactive } from 'vue'

// Exercise the production loader. Only its HTTP transport is replaced.
function fixture() {
  const source = readFileSync(new URL('../src/composables/useEnumOptions.ts', import.meta.url), 'utf8')
  const ast = ts.createSourceFile('enum.ts', source, ts.ScriptTarget.Latest, true)
  const printer = ts.createPrinter()
  const body = ast.statements.filter(node => !ts.isImportDeclaration(node)).map(node => printer.printNode(ts.EmitHint.Unspecified, node, ast)).join('\n')
  const code = ts.transpileModule(body, {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.CommonJS}}).outputText
  const calls = [], module = {exports:{}}
  new Function('reactive','request','module','exports',code)(reactive,{get:path=>new Promise((resolve,reject)=>calls.push({path,resolve,reject}))},module,module.exports)
  return {...module.exports,calls}
}
const definition = active => ({dict_code:'archive_machine_model',items:active?[{value:'12',label:'历史机型'}]:[],all_items:[{value:'12',label:'历史机型',status:active?1:0}],label_map:{12:'历史机型'}})
const tick = () => new Promise(resolve=>setImmediate(resolve))

test('late success is delivered as latest result to both consumers, not just cache', async()=>{
  const f=fixture(),old=f.loadEnumOptions('archive_machine_model'),fresh=f.loadEnumOptions('archive_machine_model',true)
  f.calls[1].resolve(definition(false));await fresh
  f.calls[0].resolve(definition(true))
  assert.equal((await old).items.length,0)
  assert.equal((await f.loadEnumOptions('archive_machine_model')).items.length,0)
})
test('obsolete failure follows latest success instead of breaking the old consumer',async()=>{
  const f=fixture(),old=f.loadEnumOptions('archive_machine_model'),handled=old.then(value=>value,error=>error)
  const fresh=f.loadEnumOptions('archive_machine_model',true);f.calls[1].resolve(definition(false));await fresh
  f.calls[0].reject(new Error('obsolete failure'))
  assert.equal((await handled).dict_code,'archive_machine_model')
})
test('old finally cannot delete a newer pending request; unforced callers join it',async()=>{
  const f=fixture(),old=f.loadEnumOptions('archive_machine_model'),fresh=f.loadEnumOptions('archive_machine_model',true)
  f.calls[0].resolve(definition(true));await tick()
  const joined=f.loadEnumOptions('archive_machine_model');await tick()
  assert.equal(f.calls.length,2)
  f.calls[1].resolve(definition(false));assert.equal((await joined).items.length,0);await Promise.all([old,fresh])
})
test('cached values are not returned while force refresh is pending',async()=>{
  const f=fixture(),first=f.loadEnumOptions('archive_machine_model');f.calls[0].resolve(definition(true));await first
  const fresh=f.loadEnumOptions('archive_machine_model',true),joined=f.loadEnumOptions('archive_machine_model');let settled=false
  joined.then(()=>{settled=true});await tick();assert.equal(settled,false)
  f.calls[1].resolve(definition(false));assert.equal((await joined).items.length,0);await fresh
})
test('latest refresh failure does not expose the older enabled cache on next load',async()=>{
  const f=fixture(),first=f.loadEnumOptions('archive_machine_model');f.calls[0].resolve(definition(true));await first
  const failed=f.loadEnumOptions('archive_machine_model',true);f.calls[1].reject(new Error('offline'));await assert.rejects(failed,/offline/)
  const retry=f.loadEnumOptions('archive_machine_model');await tick();assert.equal(f.calls.length,3)
  f.calls[2].resolve(definition(false));assert.equal((await retry).items.length,0)
})
test('latest failure also wins over late success; historical labels remain available after successful reload',async()=>{
  const f=fixture(),old=f.loadEnumOptions('archive_machine_model'),oldHandled=old.then(v=>v,e=>e)
  const fresh=f.loadEnumOptions('archive_machine_model',true);f.calls[1].reject(new Error('latest offline'));await assert.rejects(fresh,/latest offline/)
  f.calls[0].resolve(definition(true));assert.match((await oldHandled).message,/latest offline/)
  const reloaded=f.loadEnumOptions('archive_machine_model');await tick();f.calls[2].resolve(definition(false));assert.equal((await reloaded).label_map['12'],'历史机型')
})
test('independent codes deduplicate their own HTTP calls and retain numeric option compatibility',async()=>{
  const f=fixture(),one=f.loadEnumOptions('archive_machine_model'),two=f.loadEnumOptions('archive_machine_model'),other=f.loadEnumOptions('equipment_series')
  assert.equal(f.calls.length,2);f.calls[0].resolve(definition(true));f.calls[1].resolve({dict_code:'equipment_series',items:[],label_map:{}})
  await Promise.all([one,two,other]);const enums=f.useEnumOptions(['archive_machine_model']);await enums.load()
  assert.deepEqual(enums.options('archive_machine_model',true),[{value:12,label:'历史机型'}]);assert.equal(enums.label('archive_machine_model',12),'历史机型')
})
