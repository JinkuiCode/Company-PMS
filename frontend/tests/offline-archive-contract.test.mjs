import assert from 'node:assert/strict'
import {readFileSync} from 'node:fs'
import {test} from 'node:test'
import ts from 'typescript'
const view=readFileSync(new URL('../src/views/project/ProjectArchive.vue',import.meta.url),'utf8')
test('manual sync and offline controls are available',()=>{
 assert.match(view,/OfflineArchiveTools/)
 assert.match(view,/submitArchiveSync/)
 assert.match(view,/erp_sync_policy/)
 assert.match(view,/PmsNumberControl/)
})
test('offline fields keep zero and normalize empty numeric values',()=>{
 const source=readFileSync(new URL('../src/views/project/offlineArchiveFields.ts',import.meta.url),'utf8')
 const js=ts.transpileModule(source,{compilerOptions:{module:ts.ModuleKind.CommonJS}}).outputText
 const module={exports:{}};new Function('exports','module',js)(module.exports,module)
 assert.equal(module.exports.normalizeOfflineValue('quantity',0),0)
 assert.equal(module.exports.normalizeOfflineValue('quantity',''),null)
 assert.equal(module.exports.normalizeOfflineValue('archive_category','3'),3)
 assert.equal(module.exports.offlineArchiveFields.length,11)
})
