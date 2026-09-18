import assert from 'node:assert/strict'
import ts from 'typescript'
import { readFileSync } from 'node:fs'
const source = readFileSync(new URL('../src/utils/loginDestination.ts', import.meta.url), 'utf8')
const js = ts.transpileModule(source, { compilerOptions: { module: ts.ModuleKind.ESNext } }).outputText
const { safeBusinessPath, chooseLoginDestination } = await import('data:text/javascript;base64,' + Buffer.from(js).toString('base64'))
for (const path of ['https://evil.test', '//evil.test', '/\\evil', '/sso/start', '/login', '/admin/token', '/project/archive?token=secret']) assert.equal(safeBusinessPath(path), null, path)
assert.equal(safeBusinessPath('/project/archive?keyword=A'), '/project/archive?keyword=A')
const allowed = path => path.startsWith('/project/')
assert.equal(chooseLoginDestination('/project/list', '/project/archive', allowed), '/project/list')
assert.equal(chooseLoginDestination('/system/user', '/project/archive', allowed), '/project/archive')
assert.equal(chooseLoginDestination(null, '/system/user', allowed), '/403')
console.log('login destination passed')
