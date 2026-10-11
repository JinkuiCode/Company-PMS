import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
const file = new URL('../src/query-system/reference-summary.ts', import.meta.url)
const source = ts.transpileModule(readFileSync(file, 'utf8'), { compilerOptions: { module: ts.ModuleKind.ES2022 } }).outputText
const { referenceSummary } = await import('data:text/javascript;base64,' + Buffer.from(source).toString('base64'))
assert.deepEqual(referenceSummary([]), {text:'选择引用记录',title:'选择引用记录',count:0})
const records = [1,2,3,4].map(value=>({value,code:String(value),name:'产品线'+value}))
assert.deepEqual(referenceSummary([1,2,3,4,1],records), {text:'产品线1、产品线2、产品线3',title:'产品线1、产品线2、产品线3、产品线4',count:4})
assert.equal(referenceSummary(['A-202638','A-202640']).text,'A-202638、A-202640')
assert.equal(referenceSummary([1,2],records.slice(0,1)).text,'产品线1、2')
assert.equal(referenceSummary([1],[{...records[0],name:'',code:'编号1'}]).text,'编号1')
console.log('reference summary behavior passed')
