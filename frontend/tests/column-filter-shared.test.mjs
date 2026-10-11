import assert from 'node:assert/strict'
import {existsSync,readFileSync} from 'node:fs'
const file=new URL('../src/query-system/column-filters.ts',import.meta.url)
assert.ok(existsSync(file),'列漏斗必须共用独立模块')
assert.match(readFileSync(new URL('../src/query-system/PmsQueryColumnHeader.vue',import.meta.url),'utf8'), /context\.ready/,'未查询时不得读取全量列候选值')
assert.match(readFileSync(new URL('../src/styles/pms-theme.css',import.meta.url),'utf8'), /\.pms-dense-table\.el-table \.el-table__body td\.el-table__cell\.pms-query-filtered-column/,'整列填充必须覆盖第三方隔行底色')
const { matchesColumnFilters, clientColumnCandidates }=await import(file.href)
const fields=[{field:'qty',label:'数量',type:'number'},{field:'name',label:'名称',type:'text'}]
const rows=[{qty:0,name:'A'},{qty:1,name:'B'},{qty:null,name:'A'},{qty:1,name:'C'}]
assert.deepEqual(rows.filter(r=>matchesColumnFilters(r,[{field:'qty',mode:'values',values:[0,null]}],fields)),[rows[0],rows[2]])
assert.equal(rows.filter(r=>matchesColumnFilters(r,[{field:'qty',mode:'values',values:[]}],fields)).length,0)
assert.deepEqual(clientColumnCandidates(rows,fields,[{field:'name',mode:'values',values:['A']},{field:'qty',mode:'values',values:[0]}],'qty','',1).items.map(v=>v.value),[0,null])
assert.equal(clientColumnCandidates(Array.from({length:150},(_,i)=>({qty:i})),fields,[],'qty','',1).hasMore,true)
assert.equal(matchesColumnFilters(rows[0],[{field:'missing',mode:'values',values:[0]}],fields),false)
console.log('shared column filter: null/zero, empty selection, self-exclusion, all-result candidates')
