import {test} from 'node:test'
import assert from 'node:assert/strict'
import {archiveDraftIdentityErrors} from '../src/views/project/archiveDraftValidation.ts'
test('草稿编号、名称、产品线、档案类别必输，其他正式必输可空',()=>{
 assert.deepEqual(Object.keys(archiveDraftIdentityErrors({})),['project_code','project_name','product_line_id','archive_category'])
 assert.deepEqual(Object.keys(archiveDraftIdentityErrors({project_code:'  ',project_name:'项目',product_line_id:1,archive_category:2})),['project_code'])
 assert.deepEqual(Object.keys(archiveDraftIdentityErrors({project_code:'A-001',project_name:'  ',product_line_id:1,archive_category:2})),['project_name'])
 for(const value of [undefined,null,'',0,-1])assert.ok(archiveDraftIdentityErrors({project_code:'A-001',project_name:'项目',product_line_id:value,archive_category:2}).product_line_id)
 for(const value of [undefined,null,'',0,-1])assert.ok(archiveDraftIdentityErrors({project_code:'A-001',project_name:'项目',product_line_id:1,archive_category:value}).archive_category)
 assert.deepEqual(archiveDraftIdentityErrors({project_code:'A-001',project_name:'项目',product_line_id:1,archive_category:2}),{})
})
