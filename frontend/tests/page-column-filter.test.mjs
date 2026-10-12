import assert from 'node:assert/strict'
import test from 'node:test'
import { computed, effectScope, ref } from 'vue'
import { useSystemQuery } from '../src/query-system/system-adapter.ts'
const pageModule = await import('../src/query-system/page-column-filter.ts').catch(() => ({}))

test('client-paged lists paginate top results before filtering columns without changing total', () => {
  const scope=effectScope()
  scope.run(() => {
    const page=ref(2),size=ref(50),rows=Array.from({length:120},(_,i)=>({code:i}))
    const q=useSystemQuery(()=>[{field:'code',label:'编码',type:'number'}],['code'],{pagination:{page,size}})
    assert.equal(typeof q.pageRows,'function')
    q.submit([])
    assert.equal(q.topRows(rows).length,120)
    assert.equal(q.pageRows(rows).length,50)
    q.columnContext.apply('code',{field:'code',mode:'values',values:[60,110]})
    assert.deepEqual(q.pageRows(rows),[rows[60]])
    assert.equal(q.topRows(rows).length,120)
    assert.equal(page.value,2)
    page.value=3
    assert.deepEqual(q.columnFilters.value,[])
    assert.equal(q.pageRows(rows).length,20)
  })
  scope.stop()
})

test('candidates and condition filtering use only the current 50-row snapshot', async () => {
  assert.equal(typeof pageModule.usePageColumnFilter, 'function')
  const scope = effectScope()
  await scope.run(() => {
    const all = Array.from({length:279}, (_,i) => ({code:`A-${i}`,qty:i}))
    const page = ref(1), size = ref(50), filters = ref([])
    const rows = computed(() => all.slice((page.value-1)*size.value,page.value*size.value))
    const fields = () => [{field:'code',label:'项目编码',type:'text'},{field:'qty',label:'数量',type:'number'}]
    const filter = pageModule.usePageColumnFilter(rows, fields, filters, () => [page.value,size.value])
    return filter.context.load('code','',1).then(result => {
      assert.equal(result.items.length,50)
      assert.equal(result.items.some(item=>item.value==='A-50'),false)
      filter.context.apply('qty',{field:'qty',mode:'condition',condition:{id:1,field:'qty',operator:'greaterOrEqual',value:45,valueEnd:null,schemaVersion:2}})
      assert.deepEqual(filter.visibleRows.value.map(row=>row.qty),[45,46,47,48,49])
      assert.equal(page.value,1)
      page.value=2
      assert.deepEqual(filters.value,[])
      assert.equal(filter.visibleRows.value.length,50)
    })
  })
  scope.stop()
})

test('multiple columns intersect, clearing restores base page, query/new data clears stale popups', async () => {
  assert.equal(typeof pageModule.usePageColumnFilter, 'function')
  const scope = effectScope()
  await scope.run(async () => {
    const rows=ref([{name:'A',qty:0},{name:'A',qty:null},{name:'B',qty:1}]), fields=()=>[{field:'name',label:'名称',type:'text'},{field:'qty',label:'数量',type:'number'}], filters=ref([])
    const f=pageModule.usePageColumnFilter(rows,fields,filters,()=>[])
    f.context.apply('name',{field:'name',mode:'values',values:['A']})
    assert.deepEqual((await f.context.load('qty','',1)).items.map(i=>i.value),[0,null])
    f.context.apply('qty',{field:'qty',mode:'values',values:[0]})
    assert.equal(f.visibleRows.value.length,1)
    assert.deepEqual(f.filterRows([{name:'A',qty:0},{name:'B',qty:0}]),[{name:'A',qty:0}])
    assert.deepEqual((await f.context.load('qty','',1)).items.map(i=>i.value),[0,null])
    f.context.apply('name',null); f.context.apply('qty',null)
    assert.equal(f.visibleRows.value.length,3)
    f.context.apply('qty',{field:'qty',mode:'values',values:[]})
    assert.equal(f.visibleRows.value.length,0)
    rows.value=[{name:'C',qty:2}]
    assert.deepEqual(filters.value,[])
    assert.equal(f.visibleRows.value[0].name,'C')
  })
  scope.stop()
})
