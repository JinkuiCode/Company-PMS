import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import test from 'node:test'

const read = path => readFileSync(new URL(`../src/${path}`, import.meta.url), 'utf8')
const drawer = read('views/system/UserFormDrawer.vue')
assert.match(drawer, /PmsFormDrawer/)
assert.match(drawer, /账号（工号）/)
assert.match(drawer, /员工姓名/)
assert.match(drawer, /@aelsystem\.com/)
assert.match(drawer, /system:user:reset-password/)
assert.match(drawer, /reset-password/)
assert.doesNotMatch(drawer, /form\.password|创建 PMS 访问账号/)
const oa = read('views/system/OaEmployeePicker.vue')
assert.match(oa, /oa-options/)
assert.match(oa, /keyword/)
const parameters = read('views/system/ParameterList.vue')
assert.match(parameters, /system:parameter:edit/)
assert.match(parameters, /version/)
assert.doesNotMatch(parameters, /新增参数/)
assert.match(read('router/index.ts'), /must_change_password/)
assert.match(read('views/ChangePassword.vue'), /confirm_password/)
console.log('用户、参数与首次改密契约通过')

test('user drafts have a route leave guard', () => {
  assert.match(drawer, /onBeforeRouteLeave\(/)
})
for (const [name, source] of [['user', drawer], ['parameter', parameters], ['password', read('views/ChangePassword.vue')]]) {
  test(`${name} passes field semantics to controls and focuses errors after render`, () => {
    assert.match(source, /v-slot="\{ describedBy, invalid \}"/)
    assert.match(source, /:aria-describedby="describedBy"/)
    assert.match(source, /:aria-invalid="invalid"/)
    assert.match(source, /aria-required="true"/)
    assert.match(source, /await nextTick\(\)/)
    assert.match(source, /\.focus\(/)
  })
}
test('parameter group filter and newly typed secret reveal use shared controls', () => {
  assert.match(parameters, /aria-label="参数分组"/)
  assert.match(parameters, /:aria-pressed="revealSecret"/)
  assert.match(parameters, /row.sensitive \? '' : row.value/)
})
