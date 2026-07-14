import assert from 'node:assert/strict'
import { existsSync, readFileSync } from 'node:fs'
import { resolve } from 'node:path'

const root = resolve(import.meta.dirname, '..')
const read = (path) => readFileSync(resolve(root, path), 'utf8')

const packageJson = read('package.json')
const main = read('src/main.ts')
const theme = read('src/styles/pms-theme.css')
const layout = read('src/layout/AppLayout.vue')

assert.match(
  packageJson,
  /@fontsource-variable\/noto-sans-sc/,
  'Frontend should bundle Noto Sans SC instead of relying on platform-specific system fonts',
)
assert.match(
  main,
  /@fontsource-variable\/noto-sans-sc\/wght\.css/,
  'The application entry should load the bundled variable font stylesheet',
)
assert.match(theme, /--pms-font:\s*"Noto Sans SC"/, 'PMS typography should prefer the bundled Chinese font')
assert.match(theme, /--el-font-family:\s*var\(--pms-font\)/, 'Element Plus should consume the PMS font token')
assert.match(theme, /\.pms-dense-table/, 'The global theme should expose one dense Element table standard')
assert.match(theme, /\.pms-system-page/, 'The global theme should expose a standard system-page surface')

assert.match(layout, /\bSetUp\b/, 'The layout icon registry should support the field-policy SetUp icon')
assert.match(
  layout,
  /const Icons[^\n]*\bSetUp\b/,
  'The field-policy icon should be registered for dynamic menu rendering',
)

const activePages = [
  ['Dashboard.vue', 'src/views/Dashboard.vue'],
  ['UserList.vue', 'src/views/system/UserList.vue'],
  ['RoleList.vue', 'src/views/system/RoleList.vue'],
  ['EnumList.vue', 'src/views/system/EnumList.vue'],
  ['OperationLogList.vue', 'src/views/system/OperationLogList.vue'],
  ['FieldPolicyList.vue', 'src/views/system/FieldPolicyList.vue'],
]

for (const [name, path] of activePages) {
  assert.equal(existsSync(resolve(root, path)), true, `${name} should exist`)
  const source = read(path)
  assert.match(
    source,
    /pms-system-page|PmsDataList/,
    `${name} should use the shared PMS system-page or standard list shell`,
  )
  assert.doesNotMatch(
    source,
    /#409EFF|#303133|#606266|#909399|#F56C6C|#E6A23C|#67C23A/i,
    `${name} should not keep the legacy Element Plus palette`,
  )
  assert.doesNotMatch(source, /📂|📄/, `${name} should use the established icon library instead of emoji`)
}

for (const [name, path] of [
  ['Dashboard.vue', 'src/views/Dashboard.vue'],
  ['UserList.vue', 'src/views/system/UserList.vue'],
  ['RoleList.vue', 'src/views/system/RoleList.vue'],
]) {
  assert.match(read(path), /pms-dense-table/, `${name} should use the shared dense Element table class`)
}

console.log('system UI consistency contract passed')
