import {test} from 'node:test'
import assert from 'node:assert/strict'
import {governanceFieldVisible,governanceFieldRequired,orderArchiveGroups} from '../src/views/project/archiveGovernance.ts'
const main={field:'archive_category',values:[1]}
test('regional hiding does not need to change global field metadata',()=>{
 assert.equal(governanceFieldVisible('remarks',{remarks:'旧值'},false,{form_hidden:true}),false)
 assert.equal(governanceFieldVisible('serial_no',{archive_category:2,serial_no:'OLD'},false,{form_visible_when:main}),false)
 assert.equal(governanceFieldVisible('serial_no',{archive_category:1},true,{form_visible_when:main}),true)
})
test('conditionally required value is not required in another category even with old required flag',()=>{
 const policy={required:true,governance_required:true,required_when:main}
 assert.equal(governanceFieldRequired(policy,{archive_category:2},true),false)
 assert.equal(governanceFieldRequired(policy,{archive_category:1},true),true)
})
test('sales company is original basic field; empty supplementary group is removed by projection',()=>{
 const groups=orderArchiveGroups([{key:'basic',label:'基础',fields:[{key:'project_code'},{key:'customer'}]},{key:'offline',label:'补充',fields:[{key:'sales_company'}]}])
 assert.ok(groups[0].fields.some(f=>f.key==='sales_company'));assert.equal(groups.length,1)
})
import * as governance from '../src/views/project/archiveGovernance.ts'
test('fresh initialization consumes server defaults only for visible editable fields',()=>{
 assert.equal(typeof governance.archiveNewFormDefaults,'function','missing controlled fresh-form defaults')
 const fields=[{field_key:'quantity',visible:true,editable:true,default_value:1},{field_key:'quantity_unit',visible:true,editable:true,default_value:7},{field_key:'other',visible:false,editable:true,default_value:'private'}]
 assert.deepEqual(governance.archiveNewFormDefaults(fields),{quantity:1,quantity_unit:7})
 assert.deepEqual(governance.archiveNewFormDefaults([{...fields[0],editable:false},{...fields[1],default_value:null}]),{quantity_unit:null})
})
test('omitted regional values cannot be emitted as defaults; explicit correction may clear a historical serial',()=>{
 assert.equal(typeof governance.archiveCreateFieldIncluded,'function','missing regional payload projection')
 assert.equal(governance.archiveCreateFieldIncluded('remarks',{archive_category:2},{visible:true,editable:true,form_hidden:true}),false)
 assert.equal(governance.archiveCreateFieldIncluded('serial_no',{archive_category:2},{visible:true,editable:true,form_visible_when:main}),false)
 assert.equal(governance.archiveCreateFieldIncluded('serial_no',{archive_category:2},{visible:true,editable:true,form_visible_when:main},true),true)
 assert.equal(governance.archiveCreateFieldIncluded('serial_no',{archive_category:2},{visible:true,editable:false,form_visible_when:main},true),false)
})

test('category switch never bypasses configurable customer introduction cutoff',()=>{
 const policy={required:true,governance_required:false,required_effective_at:'2026-10-01',required_when:main}
 assert.equal(governanceFieldRequired(policy,{archive_category:1,created_at:'2025-01-01'},false,{archive_category:2}),false)
 assert.equal(governanceFieldRequired(policy,{archive_category:1,created_at:'2026-10-02'},false,{archive_category:2}),true)
})
test('non-main line reconciliation preserves incompatible hidden series for explicit correction',()=>{
 assert.equal(typeof governance.reconcileArchiveFormLine,'function','missing approved hidden series correction')
 const metadata={line_profiles:{1:'bench8',2:'bench12'},profiles:{bench8:{machine_model:[5],equipment_series:[6]},bench12:{machine_model:[2],equipment_series:[12]}}}
 const values={archive_category:2,product_line_id:2,machine_model:5,equipment_series:6,serial_no:'OLD'}
 const result=governance.reconcileArchiveFormLine(metadata,values,{form_visible_when:main})
 assert.equal(values.equipment_series,6);assert.equal(values.machine_model,null);assert.equal(values.serial_no,'OLD');assert.equal(result.seriesCorrection,true)
 values.product_line_id=1
 assert.equal(governance.reconcileArchiveFormLine(metadata,values,{form_visible_when:main}).seriesCorrection,false)
 const primary={archive_category:1,product_line_id:2,machine_model:5,equipment_series:6}
 governance.reconcileArchiveFormLine(metadata,primary,{form_visible_when:main});assert.equal(primary.equipment_series,null)
})
test('regional hiding preserves nonempty entered or restored values when making a new draft copy',()=>{
 assert.equal(governance.archiveCreateFieldIncluded('remarks',{remarks:'历史备注'},{visible:true,editable:true,form_hidden:true},false,true),true)
 assert.equal(governance.archiveCreateFieldIncluded('serial_no',{archive_category:2,serial_no:'HISTORY'},{visible:true,editable:true,form_visible_when:main},false,true),true)
 assert.equal(governance.archiveCreateFieldIncluded('remarks',{remarks:''},{visible:true,editable:true,form_hidden:true}),false)
 assert.equal(governance.archiveCreateFieldIncluded('customer_full_name',{customer_full_name:'原只读名称'},{visible:true,editable:false,form_hidden:true}),false)
})

test('same-id resave still omits unedited regional values; preserve mode is explicit',()=>{
 assert.equal(governance.archiveCreateFieldIncluded('remarks',{remarks:'未编辑历史'},{visible:true,editable:true,form_hidden:true}),false)
 assert.equal(governance.archiveCreateFieldIncluded('serial_no',{archive_category:2,serial_no:'OLD'},{visible:true,editable:true,form_visible_when:main}),false)
})
test('explicit clear remains an edit after switching to a category where field is hidden',()=>{
 for(const key of ['serial_no','equipment_series']){
  const policy={visible:true,editable:true,form_visible_when:main}
  assert.equal(governance.archiveCreateFieldIncluded(key,{archive_category:2,[key]:null},policy,false,false,true),true)
  assert.equal(governance.archiveCreateFieldIncluded(key,{archive_category:2,[key]:null},policy,false,true,false),false)
  assert.equal(governance.archiveCreateFieldIncluded(key,{archive_category:2,[key]:null},{...policy,editable:false},false,false,true),false)
 }
})
