import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import ts from 'typescript'
import { ref } from 'vue'
import { parse } from '@vue/compiler-sfc'

// Run the actual confirmation handlers with a delayed read-only enum refresh.
const script = parse(readFileSync(new URL('../src/views/project/ProjectArchive.vue', import.meta.url), 'utf8')).descriptor.scriptSetup.content
const ast = ts.createSourceFile('archive.ts', script, ts.ScriptTarget.Latest, true)
const names = new Set(['submitArchiveChangeRequest', 'cancelArchiveChangeConfirmation'])
const selected = ast.statements.filter(node => ts.isFunctionDeclaration(node) && names.has(node.name?.text))
assert.equal(selected.length, 2)
const code = ts.transpileModule(selected.map(node => node.getText(ast)).join('\n'), {compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
const switchCode = ts.transpileModule(readFileSync(new URL('../src/utils/detailSwitch.ts', import.meta.url),'utf8'),{compilerOptions:{module:ts.ModuleKind.ES2022}}).outputText
const { createDetailSwitch } = await import(`data:text/javascript;base64,${Buffer.from(switchCode).toString('base64')}`)
const setup = new Function('d', `const {request,focusArchiveEnumUnavailable,archiveChangeKind,archiveChangeSubmitting,archiveDrawerSaving,archiveChangeReason,archiveChangeReasonError,archiveChangeConfirmOpen,archiveChangePreview,archiveDrawerFormRef,archiveDrawerServerErrors}=d;
let archiveChangeResolve, archiveChangeArchiveId=42, archiveDrawerRevision=1, archiveChangePayload={machine_model:'12'}, archiveChangeSubmissionId='test-only';
${code}
return {submitArchiveChangeRequest,cancelArchiveChangeConfirmation,setResolver:fn=>{archiveChangeResolve=fn},hasResolver:()=>Boolean(archiveChangeResolve)};`)
const tick = () => new Promise(resolve=>setImmediate(resolve))

for (const kind of ['approval','maintenance']) {
  test(`${kind}: enum rejection settles save-and-switch despite delayed refresh and close animation`,async()=>{
    let refreshDone, refreshing=false, writes=0, resolutions=0, allowed=false, prompts=0
    const refresh = new Promise(resolve=>{refreshDone=resolve})
    const d={archiveChangeKind:ref(kind),archiveChangeSubmitting:ref(false),archiveDrawerSaving:ref(false),archiveChangeReason:ref('test reason'),archiveChangeReasonError:ref(''),archiveChangeConfirmOpen:ref(true),archiveChangePreview:ref({expected_version:1}),archiveDrawerFormRef:ref(null),archiveDrawerServerErrors:{}}
    const reject=async()=>{writes++;throw {response:{data:{detail:{code:'ARCHIVE_ENUM_UNAVAILABLE',field_key:'machine_model'}}}}}
    const page=setup({...d,request:{post:reject,put:reject},focusArchiveEnumUnavailable:async()=>{refreshing=true;await refresh}})
    const applied=[]
    const controller=createDetailSwitch(async()=>{prompts++;if(allowed)return true;return new Promise(resolve=>page.setResolver(value=>{resolutions++;resolve(value)}))},async row=>{applied.push(row)})
    const first=controller.select(2)
    await tick()
    const submit=page.submitArchiveChangeRequest()
    await tick()
    assert.equal(refreshing,true)
    assert.equal(d.archiveChangeConfirmOpen.value,false)
    // The dialog's @closed event runs while the enum fetch is still pending.
    page.cancelArchiveChangeConfirmation()
    refreshDone();await submit;await tick()
    assert.equal(resolutions,1,'failed submission must settle the waiting save exactly once')
    assert.equal(page.hasResolver(),false)
    await first
    assert.deepEqual(applied,[],'failed save must not switch records')
    assert.equal(d.archiveChangeSubmitting.value,false)
    assert.equal(d.archiveDrawerSaving.value,false)
    assert.equal(writes,1,'enum refresh must not retry the write')
    allowed=true
    await controller.select(3)
    assert.deepEqual(applied,[3],'a subsequent selection must not inherit a hung guard')
    assert.equal(prompts,2)
    page.cancelArchiveChangeConfirmation()
    assert.equal(resolutions,1)
  })
}
