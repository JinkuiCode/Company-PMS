import {test} from 'node:test'
import assert from 'node:assert/strict'
import {existsSync} from 'node:fs'
const url=new URL('../src/views/project/archive-product-line-layout.ts',import.meta.url)
const mod=existsSync(url)?await import(url.href):{}
const current=[{colId:'archive_selection',width:44,pinned:'left'},{colId:'product_line_id',width:140},{colId:'project_code',width:130,pinned:'left'},{colId:'project_name',width:190},{colId:'customer',width:150},{colId:'archive_actions',width:64,pinned:'right'}]
const legacy={selected_column_keys:['customer','project_name','project_code'],columnState:[{colId:'customer',pinned:'left',width:231,hide:false},{colId:'project_code',pinned:null,width:161,sort:'asc',sortIndex:0},{colId:'project_name',hide:true,width:301}]}
function migrate(value=legacy,allowed=true){assert.equal(typeof mod.migrateArchiveProductLineLayout,'function');return mod.migrateArchiveProductLineLayout(value,current,allowed)}
test('legacy layout puts selection then line/code left, preserves every other state and relative order',()=>{
 const original=structuredClone(legacy),next=migrate()
 assert.deepEqual(legacy,original)
 assert.equal(next.layout_version,1);assert.equal(next.selected_column_keys[0],'product_line_id')
 assert.deepEqual(next.columnState.slice(0,3).map(c=>c.colId),['archive_selection','product_line_id','project_code'])
 assert.equal(next.columnState[1].pinned,'left');assert.equal(next.columnState[2].pinned,'left')
 assert.equal(next.columnState[2].width,161);assert.equal(next.columnState[2].sort,'asc')
 assert.deepEqual(next.columnState.find(c=>c.colId==='customer'),legacy.columnState[0]);assert.deepEqual(next.columnState.find(c=>c.colId==='project_name'),legacy.columnState[2])
})
test('current layout preserves later hide/move/unpin, including an empty selection',()=>{
 const value={layout_version:1,selected_column_keys:[],columnState:[{colId:'project_name',width:245},{colId:'product_line_id',hide:true,pinned:null},{colId:'project_code',pinned:'right'}]}
 assert.deepEqual(migrate(value),value)
})
test('without list permission does not add or expose product line or stamp migration',()=>{assert.deepEqual(migrate(legacy,false),legacy)})
test('without selection tool the first actual column is product line, and duplicates cannot occur',()=>{
 assert.equal(typeof mod.migrateArchiveProductLineLayout,'function')
 const next=mod.migrateArchiveProductLineLayout({...legacy,columnState:[]},current.filter(c=>c.colId!=='archive_selection'),true)
 assert.equal(next.columnState[0].colId,'product_line_id');assert.equal(next.columnState.filter(c=>c.colId==='product_line_id').length,1)
})
test('default columns use initial pinning, never relock or force later pin state',()=>{
 assert.equal(typeof mod.archiveProductLineDefaultColumns,'function')
 const defs=mod.archiveProductLineDefaultColumns(current,true)
 assert.deepEqual(defs.slice(0,3).map(c=>c.colId),['archive_selection','product_line_id','project_code'])
 for(const c of defs.filter(c=>['product_line_id','project_code'].includes(c.colId))){assert.equal(c.initialPinned,'left');assert.equal(c.pinned,undefined);assert.equal(c.lockPinned,undefined)}
})
