import assert from 'node:assert/strict'
import { pmsActionColumn, normalizeActionColumnState } from '../src/config/listUi.ts'
assert.equal(pmsActionColumn(1).width,64)
assert.equal(pmsActionColumn(2).width,96)
assert.equal(pmsActionColumn(3).width,136)
assert.equal(pmsActionColumn(1).maxWidth,64)
const original=[{colId:'project_code',width:245,sort:'desc',pinned:'left'},{colId:'purchase_actions',width:500,flex:2,hide:true,pinned:null}]
const migrated=normalizeActionColumnState(original,'purchase_actions',1)
assert.deepEqual(migrated[0],original[0])
assert.deepEqual(migrated[1],{colId:'purchase_actions',width:64,flex:null,hide:false,pinned:'right'})
assert.equal(original[1].width,500)
console.log('Action column migration passed: compact single/two/multiple, fixed width, preserve other columns')
