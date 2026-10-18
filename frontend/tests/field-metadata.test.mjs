import assert from 'node:assert/strict'
import {test} from 'node:test'
import {existsSync} from 'node:fs'
const url=new URL('../src/form-system/fieldMetadata.ts',import.meta.url),mod=existsSync(url)?await import(url.href):{}
function resolve(...args){assert.equal(typeof mod.resolveFieldMetadata,'function');return mod.resolveFieldMetadata(...args)}
function map(...args){assert.equal(typeof mod.mapFormFieldErrors,'function');return mod.mapFormFieldErrors(...args)}
test('代码隐藏/只读是配置上限，隐藏字段不再必输或参与列表',()=>{
 const policy={visible:true,editable:true,required:true,list_available:true}
 const hidden=resolve(policy,{hidden:true});assert.equal(hidden.visible,false);assert.equal(hidden.editable,false);assert.equal(hidden.required,false);assert.equal(hidden.listAvailable,false)
 const readonly=resolve(policy,{readonly:true,readonlyReason:'来源模块维护'});assert.equal(readonly.editable,false);assert.equal(readonly.readonlyReason,'来源模块维护')
})
test('历史必填按原业务适配传入，元数据禁用不可放宽',()=>{
 assert.equal(resolve({visible:true,editable:true,required:true},{required:false}).required,false)
 const state=resolve({visible:true,editable:false,required:false,list_available:false})
 assert.equal(state.editable,false);assert.equal(state.listAvailable,false);assert.ok(state.readonlyReason)
 assert.equal(resolve(undefined).visible,true);assert.equal(resolve(undefined).editable,true)
})
test('字段错误按表单顺序，隐藏/未知字段不泄漏',()=>{
 const error={response:{data:{detail:{code:'FIELD_POLICY_VALIDATION_FAILED',fields:[{field_key:'quantity',message:'数量必须为正整数'},{field_key:'secret',message:'内部值'},{field_key:'name',message:'请填写名称'},{field_key:'unknown',message:'内部字段'}]}}}}
 const result=map(error,['name','quantity','secret'],key=>key!=='secret')
 assert.deepEqual(result,{errors:{name:'请填写名称',quantity:'数量必须为正整数'},firstField:'name'})
})
test('FastAPI字段错误和唯一性冲突复用同一适配，不把对象当文案',()=>{
 const fields=['quantity','name']
 assert.deepEqual(map({response:{data:{detail:[{loc:['body','updates','quantity'],msg:'数量错误'},{loc:['query','name'],msg:'不是表单数据'}]}}},fields,()=>true),{errors:{quantity:'数量错误'},firstField:'quantity'})
 assert.deepEqual(map({response:{data:{detail:{code:'ARCHIVE_UNIQUE_CONFLICT',field_key:'name',message:'已存在'}}}},fields,()=>true),{errors:{name:'已存在'},firstField:'name'})
 assert.deepEqual(map({response:{data:{detail:{code:'FIELD_POLICY_INVALID',fields:[{field_key:'name',message:{raw:'内部详情'}}]}}}},fields,()=>true),{errors:{name:'请检查此字段'},firstField:'name'})
})
test('非字段错误不猜测对应字段，重复错误只保留首条',()=>{
 assert.deepEqual(map({response:{data:{detail:{message:'服务器不可用'}}}},['name'],()=>true),{errors:{},firstField:null})
 const e={response:{data:{detail:{code:'FIELD_POLICY_INVALID',fields:[{field_key:'name',message:'第一条'},{field_key:'name',message:'第二条'}]}}}}
 assert.equal(map(e,['name'],()=>true).errors.name,'第一条')
})
