import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {test} from 'node:test'
import ts from 'typescript'
import {ref,computed} from 'vue'

const source=readFileSync(new URL('../src/composables/useProductLineOptions.ts',import.meta.url),'utf8')
const js=ts.transpileModule(source.replace(/^import .*$/gm,'').replace('export function','function'),
  {compilerOptions:{target:ts.ScriptTarget.ES2022,module:ts.ModuleKind.None}}).outputText
function harness(labels,options){return new Function('ref','computed','getProductLineLabels','getProductLineOptions',js+';return useProductLineOptions()')(ref,computed,labels,options)}
function gate(){let resolve;return {promise:new Promise(r=>{resolve=r}),resolve:v=>resolve(v)}}

test('ERP failure keeps independently authorized names and only current value as disabled',async()=>{
 const api=harness(async()=>({label_map:{3:'12吋Bench',4:'Single'}}),async()=>{throw Error('ERP unavailable')})
 await api.load()
 assert.equal(api.label(3),'12吋Bench')
 assert.equal(api.failed.value,true)
 assert.deepEqual(api.options.value,[])
 assert.deepEqual(api.currentOptions(3),[{value:3,label:'12吋Bench',disabled:true}])
 assert.deepEqual(api.currentOptions(null),[],'create must not receive display-only choices')
})
test('history-only current value does not enable every display name',async()=>{
 const api=harness(async()=>({label_map:{3:'历史线',4:'可选线',5:'另一历史线'}}),async()=>({options:[{value:4,label:'可选线'}]}))
 await api.load()
 assert.deepEqual(api.currentOptions(3),[{value:4,label:'可选线'},{value:3,label:'历史线',disabled:true}])
 assert.deepEqual(api.options.value,[{value:4,label:'可选线'}])
 assert.deepEqual(api.currentOptions(4),api.options.value)
})
test('failed name refresh removes stale labels and retry does not call ERP choices',async()=>{
 let fail=false,choices=0
 const api=harness(async()=>{if(fail)throw Error('unavailable');return {label_map:{3:'12吋Bench'}}},async()=>{choices++;return {options:[]}})
 await api.load();fail=true;await api.loadLabels()
 assert.equal(api.labelsFailed.value,true)
 assert.deepEqual(api.labels.value,{})
 assert.equal(api.label(3),'名称暂不可用')
 fail=false;await api.loadLabels();assert.equal(api.label(3),'12吋Bench');assert.equal(choices,1)
})
test('older name responses cannot overwrite revoked scope or a later retry',async()=>{
 const first=gate(),second=gate();let n=0
 const api=harness(()=>++n===1?first.promise:second.promise,async()=>({options:[]}))
 const old=api.loadLabels(),current=api.loadLabels()
 second.resolve({label_map:{}});await current
 first.resolve({label_map:{3:'旧权限名称'}});await old
 assert.deepEqual(api.labels.value,{})
 assert.equal(api.labelsLoading.value,false)
})
test('names become available without waiting for the independent ERP request',async()=>{
 const choices=gate()
 const api=harness(async()=>({label_map:{3:'12吋Bench'}}),()=>choices.promise)
 const loading=api.load();await Promise.resolve();await Promise.resolve()
 assert.equal(api.label(3),'12吋Bench')
 choices.resolve({options:[]});await loading
})
