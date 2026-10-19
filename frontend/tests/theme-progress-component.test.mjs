import {test} from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {parse,compileScript} from '@vue/compiler-sfc'
import ts from 'typescript'
import {createSSRApp} from 'vue'
import {renderToString} from '@vue/server-renderer'
const file=new URL('../src/theme-system/PmsProgressIndicator.vue',import.meta.url)
const {descriptor}=parse(readFileSync(file,'utf8'))
const script=compileScript(descriptor,{id:'progress-a11y',inlineTemplate:true})
const code=ts.transpileModule(script.content,{compilerOptions:{target:ts.ScriptTarget.ESNext,module:ts.ModuleKind.ESNext}}).outputText
  .replace(/from ['"]vue['"]/g,`from '${import.meta.resolve('vue')}'`)
  .replace(/from ['"]\.\/progress['"]/g,`from '${new URL('../src/theme-system/progress.ts',import.meta.url).href}'`)
const {default:component}=await import(`data:text/javascript;base64,${Buffer.from(code).toString('base64')}`)
test('progress has an accessible metric name and distinguishes rounded100 from actual completion',async()=>{
  const html=await renderToString(createSSRApp(component,{value:100,completed:2499,total:2500,label:'申请行入库率'}))
  assert.match(html,/aria-label="申请行入库率"/)
  assert.match(html,/aria-valuetext="[^"]*(持续推进|未完成)[^"]*2499\s*\/\s*2500/)
  assert.match(html,/data-progress-stage="mid"/)
})
