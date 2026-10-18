import {test} from 'node:test'
import assert from 'node:assert/strict'
import fs from 'node:fs'
import {ARCHIVE_BASIC_ORDER} from '../src/views/project/archiveGovernance.ts'
const backend=fs.readFileSync('../backend/app/services/archive_log_presentation.py','utf8')
test('shared log order stays aligned with approved create form basic order',()=>{
 const declared=backend.match(/ARCHIVE_BASIC_ORDER = \(([\s\S]*?)\)/)?.[1]
 assert.ok(declared)
 assert.deepEqual([...declared.matchAll(/'([^']+)'/g)].map(m=>m[1]),ARCHIVE_BASIC_ORDER)
})
test('create form number control does not silently clamp or round historical quantity',()=>{
 const form=fs.readFileSync('src/views/project/ArchiveRecordForm.vue','utf8')
 const number=form.match(/<PmsNumberControl[^>]+>/)?.[0]||''
 assert.match(number,/:step=/)
 assert.doesNotMatch(number,/:min=|:precision=|step-strictly/)
})
