import {test} from 'node:test'
import assert from 'node:assert/strict'
import {archiveDraftIdentityErrors} from '../src/views/project/archiveDraftValidation.ts'
test('草稿编号、名称、产品线必输，其他正式必输可空',()=>{
 assert.deepEqual(Object.keys(archiveDraftIdentityErrors({})),['project_code','project_name','product_line_id'])
 assert.deepEqual(Object.keys(archiveDraftIdentityErrors({project_code:'  ',project_name:'项目',product_line_id:1})),['project_code'])
 assert.deepEqual(Object.keys(archiveDraftIdentityErrors({project_code:'A-001',project_name:'  ',product_line_id:1})),['project_name'])
 for(const value of [undefined,null,'',0,-1])assert.ok(archiveDraftIdentityErrors({project_code:'A-001',project_name:'项目',product_line_id:value}).product_line_id)
 assert.deepEqual(archiveDraftIdentityErrors({project_code:'A-001',project_name:'项目',product_line_id:1}),{})
})
