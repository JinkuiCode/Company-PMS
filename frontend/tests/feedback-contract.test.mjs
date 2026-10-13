import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import ts from 'typescript'
const path = new URL('../src/feedback/model.ts', import.meta.url)
assert.ok(existsSync(path), 'formal feedback model has not been implemented')
const source = ts.transpileModule(readFileSync(path, 'utf8'), {compilerOptions:{module:ts.ModuleKind.ES2022}}).outputText
const { freshFeedback, categoryCode, validateFeedback, allowedOutcomes, newSubmissionId } = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`)
assert.match(newSubmissionId(), /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/)
const draft = freshFeedback()
for (const key of ['type_id','module_id','category_id','impact_id']) assert.equal(draft[key], null)
assert.equal(categoryCode(null), '')
assert.equal(categoryCode(1), 'feedback_issue_category')
assert.equal(categoryCode(2), 'feedback_request_category')
assert.ok(Object.keys(validateFeedback(draft, 'new')).length >= 7)
const valid = {...draft,type_id:1,module_id:1,category_id:1,impact_id:1,title:'标题',description:'说明',expected_result:'期望',steps:'步骤'}
assert.deepEqual(validateFeedback(valid, 'new'), {})
assert.ok(validateFeedback({...valid,steps:'  '}, 'new').steps)
assert.deepEqual(validateFeedback({...valid,type_id:2,steps:''}, 'new'), {})
assert.deepEqual(allowedOutcomes(5), [1,2,3,4])
assert.deepEqual(allowedOutcomes(6), [5,6])
assert.ok(validateFeedback({status_id:5,outcome_id:5,cause_id:1,opinion:'意见'}, 'handle').outcome_id)
for (const [file, rules] of [
 ['../src/views/feedback/FeedbackList.vue', [/PmsDataList/, /PmsQueryWorkspace/, /usePageColumnFilter/, /createDetailSwitch/, /CustomPagination/, /PMS_GRID_OPTIONS/]],
 ['../src/views/feedback/FeedbackForm.vue', [/PmsFormDrawer/, /PmsFormField/, /PmsSelectControl/, /categoryCode/]],
]) for (const rule of rules) assert.match(readFileSync(new URL(file,import.meta.url),'utf8'), rule)
console.log('feedback blank inputs, workflow and shared component contracts passed')
const formSource = readFileSync(new URL('../src/views/feedback/FeedbackForm.vue',import.meta.url),'utf8')
for (const section of ['分类与定位','提报内容','提报人信息']) assert.ok(formSource.includes(section), `missing approved A section ${section}`)
const listSource = readFileSync(new URL('../src/views/feedback/FeedbackList.vue',import.meta.url),'utf8')
assert.match(listSource, /defaultKeys=\['report_no','title','type_id'/)
assert.ok(listSource.includes('未完成'))
assert.match(listSource, /query\.applied\.value\.filter\(hasConditionValue\)/, 'empty display conditions must not become server predicates')
const detailSource = readFileSync(new URL('../src/views/feedback/FeedbackDetail.vue',import.meta.url),'utf8')
assert.ok(detailSource.includes('role="tablist"') && detailSource.includes('处理意见与结论'), 'approved A detail tabs and latest result must remain visible')
assert.match(formSource, /watch\(draft,/, 'corrected field errors must be refreshed after input')
const listAst=ts.createSourceFile('FeedbackList.ts',listSource.split('<script setup lang="ts">')[1].split('</script>')[0],ts.ScriptTarget.Latest,true)
const formClosedNode=listAst.statements.find(node=>ts.isFunctionDeclaration(node)&&node.name?.text==='formClosed')
const formClosedJs=ts.transpileModule(formClosedNode.getText(listAst),{compilerOptions:{target:ts.ScriptTarget.ES2022}}).outputText
const visibility={value:false}, currentDetail={value:{id:2}}, openDetail={value:true}, switched=[], formGuards={value:0}
const closeForm=new Function('formOpen','detail','detailOpen','switchDetail','formGuards',formClosedJs+'; return formClosed')(visibility,currentDetail,openDetail,{select:async row=>switched.push(row.id)},formGuards)
await closeForm(false)
assert.deepEqual(switched,[], 'duplicate closed-form callbacks must not replace the newly selected detail')
visibility.value=true
await closeForm(false)
assert.deepEqual(switched,[2], 'an actual form close should restore its detail')
visibility.value=true
formGuards.value=1
await closeForm(false)
assert.deepEqual(switched,[2], 'save during a pending transition must not reselect the old detail')
const drawerSource=readFileSync(new URL('../src/form-system/components/PmsFormDrawer.vue',import.meta.url),'utf8')
assert.match(drawerSource, /:modal-penetrable="penetrable"/, 'modeless detail must expose the library-supported click-through option')
assert.match(detailSource, /<PmsFormDrawer[^>]*\bpenetrable\b/, 'feedback detail must permit master row clicks')
assert.match(formSource, /<PmsFormDrawer[^>]*\bpenetrable\b/, 'feedback drafts must route master row clicks through their draft guard')
