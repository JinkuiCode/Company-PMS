import assert from 'node:assert/strict'
import {test} from 'node:test'
import fs from 'node:fs'
import {preservesLegacyManagerAddress} from '../src/views/project/archiveGovernance.ts'
const original={id:1,manager_id:997,data_origin:'kingdee_initial',governance_legacy:true,can_maintain:true,is_enabled:1,address_province:null,address_city:null,address_detail:'  历史原地址  '}
const values={manager_id:998,address_province:'',address_city:'',address_detail:'  历史原地址  '}
test('explicit owner-only maintenance preserves the unchanged historical address',()=>{
 assert.equal(preservesLegacyManagerAddress(true,original,values,{manager_id:998}),true)
})
test('ordinary editing, missing provenance/permission and unchanged or invalid owner remain strict',()=>{
 assert.equal(preservesLegacyManagerAddress(false,original,values,{manager_id:998}),false)
 for(const mutation of [{data_origin:'pms'},{data_origin:'offline_initial'},{governance_legacy:false},{governance_legacy:undefined},{can_maintain:false},{is_enabled:0}])assert.equal(preservesLegacyManagerAddress(true,{...original,...mutation},values,{manager_id:998}),false)
 for(const manager_id of [997,null,0,'998'])assert.equal(preservesLegacyManagerAddress(true,original,{...values,manager_id},{manager_id}),false)
})
test('every extra key, even unchanged, and every changed address byte disqualifies the exception',()=>{
 for(const key of ['project_name','customer','serial_no','address_province','address_city','address_detail'])assert.equal(preservesLegacyManagerAddress(true,original,values,{manager_id:998,[key]:original[key]}),false)
 for(const [key,value]of [['address_province','32'],['address_city','3202'],['address_detail','历史原地址']])assert.equal(preservesLegacyManagerAddress(true,original,{...values,[key]:value},{manager_id:998}),false)
 assert.equal(preservesLegacyManagerAddress(true,original,values,{}),false)
})
test('drawer uses the narrow address exception independently of historical required-field compatibility',()=>{
 const source=fs.readFileSync(new URL('../src/views/project/ProjectArchive.vue',import.meta.url),'utf8')
 assert.match(source,/preservesLegacyManagerAddress\(archiveMaintenanceMode\.value, selectedArchive\.value, values, buildArchiveDrawerPayload\(\)\)/)
 assert.match(source,/selectedArchive\.value\?\.data_origin === 'offline_initial'/)
 assert.doesNotMatch(source,/historical\s*=.*kingdee_initial/)
})
