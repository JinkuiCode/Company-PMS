import assert from 'node:assert/strict'
import { test } from 'node:test'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { computed, nextTick, reactive, ref, toRaw, watch, effectScope } from 'vue'
import { useFormSession } from '../src/form-system/useFormSession.ts'
import { freshFeedback, categoryCode, allowedOutcomes, validateFeedback } from '../src/feedback/model.ts'
const text=readFileSync(new URL('../src/views/feedback/FeedbackForm.vue',import.meta.url),'utf8').split('<script setup lang="ts">')[1].split('</script>')[0]
const ast=ts.createSourceFile('FeedbackForm.ts',text,ts.ScriptTarget.Latest,true)
const source=ast.statements.filter(node=>!ts.isImportDeclaration(node)).map(node=>node.getText(ast)).join('\n')
const js=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
function deferred(){let resolve;const promise=new Promise(ok=>resolve=ok);return {promise,resolve}}
async function setup({decision=async()=> 'cancel',submit,upload,mode='new',row=null}={}){
 const scope=effectScope(),props=reactive({modelValue:false,mode,row}),events=[],writes=[],uploads=[],messages=[]
 const bindings={computed,nextTick,ref,watch,toRaw,useFormSession,freshFeedback,categoryCode,allowedOutcomes,validateFeedback,
  newSubmissionId:()=> '11111111-1111-4111-8111-111111111111',
  useAuthStore:()=>({user:{real_name:'隔离测试',email:'fixture@example.invalid'}}),
  defineExpose:()=>{},defineProps:()=>props,defineEmits:()=>((event,value)=>{events.push([event,value]);if(event==='update:modelValue')props.modelValue=value}),
  ElMessage:{success:value=>messages.push(value),warning:value=>messages.push(value)},confirmDetailSwitch:decision,
  submitFeedback:async data=>{writes.push(['create',structuredClone(data)]);return submit?submit(data):{id:31,version:1}},
  handleFeedback:async(id,data)=>{writes.push(['handle',id,structuredClone(data)]);return{id,version:6}},
  supplementFeedback:async(id,data)=>{writes.push(['supplement',id,structuredClone(data)]);return{id,version:6}},
  uploadFeedbackFile:async(saved,file,submission)=>{uploads.push({version:saved.version,file:file.name,submission});return upload?upload(saved,file):{version:saved.version+1}},
  document:{getElementById:()=>({focus(){}})}}
 const f=scope.run(()=>new Function(...Object.keys(bindings),js+';return {guard,close,save,draft,files,dirty,busy,banner,saved};')(...Object.values(bindings)))
 props.modelValue=true;await nextTick()
 return {f,props,events,writes,uploads,messages,stop:()=>scope.stop()}
}
function fill(h){Object.assign(h.f.draft.value,{type_id:1,module_id:1,category_id:1,impact_id:1,title:'隔离测试',description:'仅模拟',expected_result:'正确反馈',steps:'模拟操作'})}

test('并发关闭只确认一次，取消保留填写且不写入',async()=>{
 const gate=deferred();let count=0;const h=await setup({decision:()=>{count++;return gate.promise}})
 try{h.f.draft.value.title='未存内容';const a=h.f.guard(),b=h.f.guard();assert.equal(count,1);gate.resolve('cancel');assert.deepEqual(await Promise.all([a,b]),[false,false]);assert.equal(h.f.draft.value.title,'未存内容');assert.equal(h.writes.length,0)}finally{gate.resolve('cancel');h.stop()}
})
test('干净表单直接关闭；仅附件变化也要确认；放弃不提交',async()=>{
 let count=0;const h=await setup({decision:async()=>{count++;return 'discard'}})
 try{assert.equal(await h.f.guard(),true);assert.equal(count,0);h.f.files.value=[new File(['fixture'],'a.pdf')];assert.equal(h.f.dirty.value,true);assert.equal(await h.f.guard(),true);assert.equal(count,1);assert.equal(h.writes.length,0)}finally{h.stop()}
})
test('确认选择保存只创建一次，成功才允许关闭',async()=>{
 const gate=deferred();let count=0;const h=await setup({decision:()=>{count++;return gate.promise}})
 try{fill(h);const a=h.f.guard(),b=h.f.guard();gate.resolve('save');const results=await Promise.all([a,b]);assert.deepEqual(results,[true,false]);assert.equal(count,1);assert.equal(h.writes.length,1);assert.equal(h.writes[0][1].submission_id,'11111111-1111-4111-8111-111111111111');assert.equal(h.props.modelValue,false);assert.equal(h.f.dirty.value,false);assert.equal(await h.f.guard(),true);assert.equal(count,1)}finally{gate.resolve('cancel');h.stop()}
})
test('保存409时不关闭，释放关闭锁后可取消，保留正文及冲突提示',async()=>{
 let choice='save';const h=await setup({decision:async()=>choice,submit:async()=>{throw {response:{status:409}}}})
 try{fill(h);assert.equal(await h.f.guard(),false);assert.equal(h.props.modelValue,true);assert.match(h.f.banner.value,/记录已被修改/);choice='cancel';assert.equal(await h.f.guard(),false);assert.equal(h.writes.length,1);assert.equal(h.f.draft.value.title,'隔离测试')}finally{h.stop()}
})
test('正文已保存而附件失败，关闭后选保存仅续传附件，不重复创建正文',async()=>{
 let fail=true;const h=await setup({decision:async()=> 'save',upload:async row=>{if(fail)throw Error('fixture upload failed');return {version:row.version+1}}})
 try{fill(h);h.f.files.value=[new File(['fixture'],'a.pdf')];assert.equal(await h.f.guard(),false);assert.equal(h.writes.length,1);assert.match(h.f.banner.value,/内容已保存/);assert.equal(h.f.files.value.length,1);fail=false;assert.equal(await h.f.guard(),true);assert.equal(h.writes.length,1);assert.equal(h.uploads.length,2);assert.equal(h.uploads[1].version,1);assert.equal(h.uploads[1].submission,'11111111-1111-4111-8111-111111111111');assert.equal(h.f.files.value.length,0)}finally{h.stop()}
})
test('处理与补充仍携带原单据版本，打开新会话重建基线',async()=>{
 for(const mode of ['handle','supplement']){
  const h=await setup({mode,row:{id:77,version:5,status_id:1},decision:async()=> 'save'})
  try{if(mode==='handle')h.f.draft.value.opinion='隔离处理';else h.f.draft.value.description='隔离补充';assert.equal(await h.f.guard(),true);assert.equal(h.writes.length,1);assert.equal(h.writes[0][0],mode);assert.equal(h.writes[0][1],77);assert.equal(h.writes[0][2].version,5);h.props.modelValue=true;await nextTick();assert.equal(h.f.dirty.value,false)}finally{h.stop()}
 }
})
