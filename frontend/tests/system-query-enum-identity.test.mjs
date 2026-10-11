import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { parse } from '@vue/compiler-sfc'
import { computed, reactive, ref, watch, nextTick } from 'vue'
import { useSystemQuery } from '../src/query-system/system-adapter.ts'

const source = readFileSync(new URL('../src/views/system/EnumList.vue', import.meta.url), 'utf8')
const script = parse(source).descriptor.scriptSetup.content
const ast = ts.createSourceFile('EnumList.ts', script, ts.ScriptTarget.Latest, true)
const printer = ts.createPrinter()
const body = ast.statements.filter(statement => !ts.isImportDeclaration(statement)).map(statement => printer.printNode(ts.EmitHint.Unspecified, statement, ast)).join('\n')
const code = ts.transpileModule(body, {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText
const setup = new Function('dependencies', `const {computed,reactive,ref,watch,onMounted,onBeforeUnmount,onUnmounted,ElMessage,ElMessageBox,loadEnumOptions,useAuthStore,request,useSystemQuery} = dependencies;\n${code}\nreturn {fetchDicts,fetchItems,selectDict,selectedDict,dictItems,queryDraft,filteredItems,columnContext,itemsLoading,submitQuery};`)
const definitions = [{id:1,dict_code:'enum_a',dict_name:'A'},{id:2,dict_code:'enum_b',dict_name:'B'}]
const rowsA = [{id:11,item_value:'11',item_label:'Alpha',status:1},{id:12,item_value:'12',item_label:'Beta',status:0}]
const rowsB = [{id:21,item_value:'21',item_label:'Gamma',status:1},{id:22,item_value:'22',item_label:'Delta',status:0}]
async function settle() { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
async function fixture() {
  const requests = [], unmount = [], errors = []
  const page = setup({computed,reactive,ref,watch,useSystemQuery,onMounted:()=>{},onBeforeUnmount:fn=>unmount.push(fn),onUnmounted:fn=>unmount.push(fn),
    ElMessage:{error:message=>errors.push(message)},ElMessageBox:{},loadEnumOptions:async()=>{},useAuthStore:()=>({hasPermission:()=>false}),
    request:{get:path=>path==='/dicts' ? Promise.resolve(definitions) : new Promise((resolve,reject)=>requests.push({path,resolve,reject}))},
  })
  await page.fetchDicts()
  await settle()
  return {page,requests,errors,unmount}
}

test('late A response cannot overwrite accepted B rows or clear B loading', async () => {
  const {page,requests} = await fixture()
  page.selectDict(2)
  await settle()
  requests[1].resolve(rowsB)
  await settle()
  assert.equal(page.selectedDict.value.dict_code,'enum_b')
  assert.deepEqual(page.dictItems.value,rowsB)
  requests[0].resolve(rowsA)
  await settle()
  assert.deepEqual(page.dictItems.value,rowsB,'标题B的数据不得被迟到A覆盖')
})

test('switch clears A accepted query and columns, B candidates come only from B', async () => {
  const {page,requests} = await fixture()
  requests[0].resolve(rowsA)
  await settle()
  const condition = {id:1,field:'item_label',operator:'contains',value:'Beta',valueEnd:null,schemaVersion:2}
  page.queryDraft.value = [condition]
  page.submitQuery([condition])
  page.columnContext.apply('status',{field:'status',mode:'values',values:[0]})
  assert.deepEqual(page.filteredItems.value, [rowsA[1]])
  page.selectDict(2)
  await settle()
  assert.deepEqual(page.queryDraft.value,[],'切换立即清空临时草稿')
  assert.deepEqual(page.columnContext.filters(),[],'切换立即清空A列筛选')
  assert.equal(page.columnContext.ready(),false,'B尚未接受结果不能取A候选')
  requests[1].resolve(rowsB)
  await settle()
  assert.deepEqual(page.filteredItems.value,rowsB,'B无需再次点查询即可展示不受A条件限制的结果')
  assert.deepEqual((await page.columnContext.load('item_label','',1)).items.map(item=>item.label),['Gamma','Delta'])
})

test('A to B to A rejects first A response even though active code matches again', async () => {
  const {page,requests} = await fixture()
  page.selectDict(2)
  page.selectDict(1)
  await settle()
  requests[0].resolve(rowsA)
  await settle()
  assert.equal(page.itemsLoading.value,true,'旧A完成不能解除最新A加载状态')
  assert.deepEqual(page.dictItems.value,[])
  requests[2].resolve([rowsA[1]])
  await settle()
  requests[1].resolve(rowsB)
  await settle()
  assert.deepEqual(page.dictItems.value,[rowsA[1]])
  assert.equal(page.itemsLoading.value,false)
})

test('only latest refresh for same enum is accepted', async () => {
  const {page,requests} = await fixture()
  const latest = page.fetchItems()
  requests[1].resolve([rowsA[1]])
  await latest
  requests[0].resolve(rowsA)
  await settle()
  assert.deepEqual(page.dictItems.value,[rowsA[1]])
})

test('late failure cannot unlock newer loading or report an error for another enum', async () => {
  const {page,requests,errors} = await fixture()
  page.selectDict(2)
  requests[0].reject(Error('stale A'))
  await settle()
  assert.equal(page.itemsLoading.value,true)
  assert.equal(page.columnContext.ready(),false)
  assert.deepEqual(errors,[])
  requests[1].resolve(rowsB)
  await settle()
  assert.deepEqual(page.filteredItems.value,rowsB)
})

test('unmounted page cannot accept an outstanding response', async () => {
  const {page,requests,unmount} = await fixture()
  unmount.forEach(dispose=>dispose())
  requests[0].resolve(rowsA)
  await settle()
  assert.deepEqual(page.dictItems.value,[])
  assert.equal(page.columnContext.ready(),false)
})
