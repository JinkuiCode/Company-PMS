import assert from 'node:assert/strict'
import {test} from 'node:test'
import {orderArchiveGroups,governanceFieldVisible,governanceFieldRequired} from '../src/views/project/archiveGovernance.ts'
test('approved basic order has no duplicates or plan fields',()=>{
 const keys=['project_code','project_name','customer','manager_id','equipment_series','serial_no','product_line_id','archive_category','machine_model','quantity','quantity_unit']
 const result=orderArchiveGroups([{key:'basic',label:'基础',fields:keys.slice(0,7).map(key=>({key}))},{key:'offline',label:'补充',fields:[...keys.slice(7).map(key=>({key})),{key:'remarks'}]},{key:'plan',label:'计划',fields:[{key:'plan_start_date'}]}])
 assert.deepEqual(result[0].fields.map(field=>field.key),['archive_category','project_code','project_name','customer','product_line_id','quantity','quantity_unit','manager_id','machine_model','equipment_series','serial_no'])
 assert.equal(new Set(result.flatMap(group=>group.fields.map(field=>field.key))).size,12)
 assert.ok(!result.some(group=>group.key==='plan'))
})
test('historical fullname is display-only and never offered on create',()=>{
 assert.equal(governanceFieldVisible('customer_full_name',{customer_full_name:''}),false)
 assert.equal(governanceFieldVisible('customer_full_name',{customer_full_name:'历史全名'}),true)
 assert.equal(governanceFieldVisible('customer_full_name',{customer_full_name:'历史全名'},true),false)
})
test('main-machine required metadata uses immutable historic classification',()=>{
 const policy={required:false,governance_required:true,required_when:{field:'archive_category',values:[1]},required_effective_at:'2026-10-14T10:00:00'}
 assert.equal(governanceFieldRequired(policy,{archive_category:1},true),true)
 assert.equal(governanceFieldRequired(policy,{archive_category:2},true),false)
 assert.equal(governanceFieldRequired(policy,{archive_category:1,governance_legacy:true,created_at:'2027-01-01'},false),false)
 assert.equal(governanceFieldRequired(policy,{archive_category:1,governance_legacy:false,created_at:'2000-01-01'},false),true)
 assert.equal(governanceFieldRequired(policy,{archive_category:1,governance_legacy:true},false,{archive_category:2}),true)
})
