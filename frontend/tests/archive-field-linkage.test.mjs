import {test} from 'node:test'
import assert from 'node:assert/strict'
import {filterArchiveLinkedOptions, reconcileArchiveLinkedFields} from '../src/views/project/archiveFieldLinkage.ts'
const metadata={line_profiles:{1:'bench8',2:'bench12',3:'single'},profiles:{bench8:{machine_model:[5],equipment_series:[6]},bench12:{machine_model:[2],equipment_series:[12]},single:{machine_model:[1],equipment_series:[14]}}}
test('按父产品线过滤已确认分组，保留未归属通用项和原状态',()=>{
 const options=[{value:1,label:'Single'},{value:2,label:'12吋'},{value:5,label:'8吋'},{value:16,label:'辅机',disabled:true}]
 assert.deepEqual(filterArchiveLinkedOptions(metadata,1,'machine_model',options),[options[2],options[3]])
 assert.deepEqual(filterArchiveLinkedOptions(metadata,4,'machine_model',options),options)
 assert.deepEqual(filterArchiveLinkedOptions(metadata,null,'machine_model',options),options)
 assert.deepEqual(filterArchiveLinkedOptions(metadata,1,'quantity_unit',options),options)
})
test('只清不兼容子项，保留通用值、兼容值及其他字段，不倒推产品线',()=>{
 const values={product_line_id:1,machine_model:2,equipment_series:6,project_name:'原名'}
 assert.deepEqual(reconcileArchiveLinkedFields(metadata,values),['machine_model'])
 assert.deepEqual(values,{product_line_id:1,machine_model:null,equipment_series:6,project_name:'原名'})
 const general={product_line_id:1,machine_model:16,equipment_series:18}
 assert.deepEqual(reconcileArchiveLinkedFields(metadata,general),[])
})
