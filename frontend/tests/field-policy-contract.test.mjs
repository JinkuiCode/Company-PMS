import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

const read = (path) => readFileSync(new URL(`../${path}`, import.meta.url), 'utf8')

const view = read('src/views/system/FieldPolicyList.vue')
const router = read('src/router/index.ts')
const projectList = read('src/views/project/ProjectList.vue')
const archive = read('src/views/project/ProjectArchive.vue')
const request = read('src/utils/request.ts')

assert.match(view, /PmsDataList/)
assert.match(view, /项目档案/)
assert.match(view, /项目进度/)
assert.match(view, /field-policies/)
assert.match(view, /恢复默认/)
assert.match(view, /批量保存/)
assert.match(view, /required/)
assert.match(view, /list_available/)
assert.match(router, /system\/field-policy/)
assert.match(router, /system:field-policy:view/)

assert.match(projectList, /sheet_values/)
assert.match(projectList, /dynamicRequiredFields/)
assert.match(projectList, /field\.visible/)
assert.match(projectList, /required/)
assert.match(projectList, /focusProjectPolicyValidation/)
assert.match(archive, /archives\/fields/)
assert.match(archive, /effectiveArchiveFields/)
assert.match(archive, /field\.visible/)
assert.match(archive, /field\.required/)
assert.match(archive, /focusArchivePolicyValidation/)
assert.match(request, /FIELD_POLICY_VALIDATION_FAILED/)
assert.match(request, /structured\.fields/)

console.log('field policy contract passed')
