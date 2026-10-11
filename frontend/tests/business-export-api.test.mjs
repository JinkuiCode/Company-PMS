import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import vm from 'node:vm'
import ts from 'typescript'

const source = new URL('../src/api/businessExport.ts', import.meta.url)
assert.ok(existsSync(source), 'Business XLSX export needs its own API, not an ERP report job')
const compiled = ts.transpileModule(readFileSync(source, 'utf8'), { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.CommonJS } }).outputText
const calls = [], blob = new Blob(['xlsx'])
const request = { post: async (...args) => { calls.push(args); return blob } }
const sandbox = { exports: {}, require: () => ({ __esModule: true, default: request }) }
vm.runInNewContext(compiled, sandbox)
const { downloadBusinessExport, businessExportPermission, businessViewPermission, businessExportFilename } = sandbox.exports
const snapshot = { parameters: {}, filters: [], column_filters: [], sort: [], columns: ['project_name'] }
for (const [resource, path, name, prefix] of [
  [{ kind: 'projects' }, '/projects/export', '项目列表.xlsx', 'project:list'],
  [{ kind: 'tasks', projectId: 8 }, '/projects/8/tasks/export', '项目进度.xlsx', 'project:list'],
  [{ kind: 'archives' }, '/projects/archives/export', '项目档案.xlsx', 'project:archive'],
]) {
  assert.equal(await downloadBusinessExport(resource, snapshot), blob)
  const [url, body, config] = calls.at(-1)
  assert.equal(url, path)
  assert.deepEqual(body, snapshot)
  assert.equal(config.responseType, 'blob')
  assert.equal(config.timeout, 0)
  assert.equal(businessExportPermission(resource), `${prefix}:export`)
  assert.equal(businessViewPermission(resource), `${prefix}:view`)
  assert.equal(businessExportFilename(resource), name)
}
for (const projectId of [0, -1, 1.5, NaN, '8/../../archives']) {
  await assert.rejects(async () => downloadBusinessExport({ kind: 'tasks', projectId }, snapshot), /项目/)
}
assert.equal(calls.length, 3, 'Invalid task identity cannot target a different endpoint')
console.log('business export API passed: scoped endpoints, permission names, Chinese XLSX filenames and task identity')
