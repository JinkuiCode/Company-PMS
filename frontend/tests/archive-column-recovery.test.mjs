import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import ts from 'typescript'
import vm from 'node:vm'
import {createColumnPreferences,normalizeColumnPreference} from '../src/list-system/columnPreferences.ts'
import {migrateArchiveProductLineLayout,ARCHIVE_PRODUCT_LINE_LAYOUT_VERSION} from '../src/views/project/archive-product-line-layout.ts'
const source=fs.readFileSync(new URL('../src/views/project/ProjectArchive.vue',import.meta.url),'utf8')
const extracted=source.slice(source.indexOf('function normalizeArchiveColumnKeys('),source.indexOf('function handleArchiveColumnSelection('))
function fixture(failAt){
 const old={selected_column_keys:['customer','project_code','project_name'],columnState:[{colId:'customer',width:231,pinned:'left',hide:false},{colId:'project_code',width:161,pinned:null},{colId:'project_name',width:291,hide:true}]}
 const original=JSON.stringify(old);let stored=original,reads=0,writes=0
 const storage={getItem(){if(++reads===failAt)throw Error('temporary read failure');return stored},setItem(key,value){writes++;stored=value},removeItem(){}}
 const state=[{colId:'product_line_id',width:140,pinned:'left'},{colId:'project_code',width:130,pinned:'left'},{colId:'project_name',width:190,hide:true},{colId:'customer',width:150,hide:false}]
 const allowed=new Set(state.map(c=>c.colId))
 const ctx={normalizeColumnPreference,migrateArchiveProductLineLayout,ARCHIVE_PRODUCT_LINE_LAYOUT_VERSION,
  defaultArchiveColumnKeys:{value:[...allowed]},availableArchiveColumnKeys:{value:allowed},baseArchiveColumnKeys:[...allowed],fixedArchiveColumnKeys:new Set(),
  selectedArchiveColumnKeys:{value:[]},archiveLayoutVersion:{value:undefined},archiveColumnPreferencesReady:{value:false},archiveColumnPreferenceWritesEnabled:{value:false},archiveColumnStateRestored:{value:false},restoringArchiveColumnState:{value:false},
  archiveColumnListAvailable:()=>true,archiveColumnSchema:()=>({allowed,defaults:[...allowed],fixed:new Set(),layoutVersion:1}),
  archiveColumnPreferences:createColumnPreferences({pageKey:'project-archive',ownerId:()=>1,storage:()=>storage}),localStorage:storage,LEGACY_ARCHIVE_LAYOUT_KEY:'legacy',warnArchiveColumnStorage:()=>{},scheduleArchiveScrollbarMetrics:()=>{},
  gridApi:{getColumnState:()=>structuredClone(state),applyColumnState({state:changes,applyOrder}){for(const change of changes){const row=state.find(c=>c.colId===change.colId);if(row)Object.assign(row,change)}if(applyOrder)state.sort((a,b)=>changes.findIndex(c=>c.colId===a.colId)-changes.findIndex(c=>c.colId===b.colId))}},}
 vm.createContext(ctx);vm.runInContext(ts.transpileModule(extracted,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText,ctx)
 vm.runInContext('if(typeof initializeArchiveColumnPreferences === "function") initializeArchiveColumnPreferences(); else restoreSelectedArchiveColumnKeys(); archiveColumnPreferencesReady.value=true; completeArchiveColumnPreferenceRestore()',ctx)
 return {state,original,stored,reads,writes}
}
test('intermittent second read failure cannot replace restored widths with defaults or mark success',()=>{
 const f=fixture(2)
 assert.equal(f.state.find(c=>c.colId==='customer').width,231)
 assert.equal(f.writes,0);assert.equal(f.stored,f.original)
})
test('first read failure keeps original string and never automatically stamps migration',()=>{
 const f=fixture(1)
 assert.equal(f.writes,0);assert.equal(f.stored,f.original)
})
