import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {test} from 'node:test'
import ts from 'typescript'
function harness(){
 const source=readFileSync(new URL('../src/views/project/OfflineArchiveTools.vue',import.meta.url),'utf8').split('<script setup lang="ts">')[1].split('</script>')[0].replace(/^import .*$/gm,'')
 const js=ts.transpileModule(source,{compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText
 const calls=[];const request={async post(url,data,config={}){
  calls.push({url,config});const simulatedDuration=url.endsWith('workbook')?1700:url.endsWith('preview')?31000:90000
  if((config.timeout??15000)<simulatedDuration)throw new Error('server response exceeds request wait budget')
  if(url.endsWith('workbook'))return {errors:[],payload:{rows:[]}}
  if(url.endsWith('preview'))return {errors:[],created:2706,updated:318,unchanged:0,total:3024}
  return {batch_id:1,msg:'import completed'}
 }}
 const evaluate=new Function('ref','useAuthStore','useProductLineOptions','request','defineProps','defineEmits','ElMessage','ElMessageBox',js+';return {chooseFile,applyImport,errors,preview,batchId}')
 const api=evaluate(v=>({value:v}),()=>({}),()=>({load:async()=>{}}),request,()=>({selectedRows:[]}),()=>()=>{}, {success(){}},{confirm:async()=>{}})
 return {api,calls}
}
test('approved large archive can complete preview and apply within import request budgets',async()=>{
 const {api,calls}=harness();await api.chooseFile({target:{files:[new File(['test'],'archive.xlsx')]}})
 assert.deepEqual(api.errors.value,[],'31-second preview must complete')
 assert.equal(api.preview.value.total,3024)
 await api.applyImport();assert.equal(api.batchId.value,1,'90-second atomic import must return its receipt')
 assert.deepEqual(calls.map(c=>c.url),['/offline-archives/workbook','/offline-archives/preview','/offline-archives/apply'])
 for(const call of calls)assert.ok(call.config.timeout>0&&call.config.timeout<=120000,'wait remains bounded')
})
