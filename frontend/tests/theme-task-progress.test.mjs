import {test} from 'node:test'
import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import ts from 'typescript'
import {progressAppearance} from '../src/theme-system/progress.ts'
const source=readFileSync(new URL('../src/views/project/ProjectProgress.vue',import.meta.url),'utf8')
const body=source.match(/const totalProgress = computed\(\(\) => \{([\s\S]*?)\n\}\)/)[1]
const color=source.match(/function progressColor\(v: number\) \{[^\n]+/)[0]
function actualPage(rows){
  const code=ts.transpileModule(`${color}\nreturn {display:(()=>{${body}})(),color:progressColor}`,{compilerOptions:{target:ts.ScriptTarget.ESNext}}).outputText
  return new Function('rowData','progressAppearance',code)({value:rows},progressAppearance)
}
test('task page keeps rounded display but uses unrounded task evidence for complete color',()=>{
  const incomplete=actualPage([{progress:100},{progress:99}])
  assert.equal(incomplete.display,100)
  assert.equal(incomplete.color(incomplete.display),'var(--pms-progress-mid,#b68b00)')
  const complete=actualPage([{progress:100},{progress:100}])
  assert.equal(complete.color(complete.display),'var(--pms-progress-complete,#087e65)')
})
