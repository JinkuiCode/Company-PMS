<script setup lang="ts">
import { computed, nextTick, reactive, ref, watch } from 'vue'
import { onBeforeRouteLeave } from 'vue-router'
import { ElMessage, ElMessageBox } from 'element-plus'
import { Connection } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'
import { PmsFormDrawer, PmsFormField, PmsTextControl, PmsTreeSelectControl, PmsSelectControl, PmsSwitchControl, type PmsOption } from '@/form-system'
import OaEmployeePicker, { type OaEmployee } from './OaEmployeePicker.vue'

const props = defineProps<{ modelValue: boolean; user?: any; departments: any[]; roles: PmsOption[]; defaultDept: number | null }>()
const emit = defineEmits<{ 'update:modelValue': [value: boolean]; saved: [] }>()
const auth = useAuthStore()
const editing = computed(() => Boolean(props.user?.id))
const canEdit = computed(() => auth.hasPermission(editing.value ? 'system:user:edit' : 'system:user:add'))
const busy = ref(false)
const resetting = ref(false)
const oaVisible = ref(false)
const errors = reactive<Record<string, string>>({})
const formElement = ref<HTMLFormElement>()
const form = reactive({ username: '', real_name: '', email: '@aelsystem.com', mobile: '', dept_id: null as number | null, role_ids: [] as number[], status: 1 })
const validEmail = (email: string) => !email.trim() || /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email.trim())
watch(() => form.username, value => { if (value.trim()) delete errors.username })
watch(() => form.real_name, value => { if (value.trim()) delete errors.real_name })
watch(() => form.email, value => { if (validEmail(value)) delete errors.email })
let original = ''
watch(() => props.modelValue, open => {
  if (!open) return
  const row = props.user
  Object.assign(form, { username: row?.username || '', real_name: row?.real_name || '', email: row ? row.email || '' : '@aelsystem.com', mobile: row?.mobile || '', dept_id: row ? row.dept_id ?? null : props.defaultDept, role_ids: [...(row?.role_ids || [])], status: row?.status ?? 1 })
  Object.keys(errors).forEach(key => delete errors[key])
  original = JSON.stringify(form)
})
async function canLeave() {
  if (busy.value || resetting.value) return false
  if (props.modelValue && JSON.stringify(form) !== original) {
    try { await ElMessageBox.confirm('尚有未保存的用户资料，确定关闭吗？', '未保存修改', { type: 'warning', confirmButtonText: '关闭', cancelButtonText: '继续编辑' }) }
    catch { return false }
  }
  return true
}
async function beforeClose(done: () => void) {
  if (await canLeave()) done()
}
onBeforeRouteLeave(canLeave)
async function focusFirstInvalid() {
  await nextTick()
  formElement.value?.querySelector<HTMLElement>('[aria-invalid="true"]:not(:disabled)')?.focus()
}
function close() { void beforeClose(() => emit('update:modelValue', false)) }
function useEmployee(employee: OaEmployee) { form.username = employee.username; form.real_name = employee.real_name; delete errors.username; delete errors.real_name }
function validate() {
  Object.keys(errors).forEach(key => delete errors[key])
  if (!form.username.trim()) errors.username = '请输入账号（工号）'
  if (!form.real_name.trim()) errors.real_name = '请输入员工姓名'
  if (!validEmail(form.email)) errors.email = '请补全邮箱地址，或清空后保存'
  return !Object.keys(errors).length
}
async function save() {
  if (busy.value || !canEdit.value) return
  if (!validate()) { await focusFirstInvalid(); return }
  busy.value = true
  const values = { real_name: form.real_name.trim(), email: form.email.trim() || null, mobile: form.mobile.trim() || null, dept_id: form.dept_id, role_ids: form.role_ids, status: form.status }
  try {
    if (editing.value) await request.put(`/users/${props.user.id}`, values)
    else await request.post('/users', { ...values, username: form.username.trim() })
    ElMessage.success(editing.value ? '用户已更新' : '用户已创建')
    original = JSON.stringify(form)
    emit('update:modelValue', false)
    if (editing.value && props.user.id === auth.user?.id) await auth.fetchUser()
    emit('saved')
  } catch (error: any) {
    const detail = error.response?.data?.detail
    if (Array.isArray(detail)) detail.forEach(item => { const key = item.loc?.at(-1); if (key && key in form) errors[key] = item.msg })
  } finally { busy.value = false; await focusFirstInvalid() }
}
async function resetPassword() {
  if (resetting.value || !auth.hasPermission('system:user:reset-password')) return
  try { await ElMessageBox.confirm(`将 ${form.username} 的密码重置为当前“用户初始密码”。原登录凭据将失效，下次密码登录必须改密；不会修改 OA 密码或保存当前资料。`, '重置密码', { type: 'warning', confirmButtonText: '确认重置', cancelButtonText: '取消' }) }
  catch { return }
  resetting.value = true
  try {
    await request.post(`/users/${props.user.id}/reset-password`)
    ElMessage.success('已重置为当前初始密码')
    if (props.user.id === auth.user?.id) { auth.logout(); window.location.href = '/login' }
  } finally { resetting.value = false }
}
</script>

<template>
  <PmsFormDrawer :model-value="modelValue" :title="editing ? (canEdit ? '编辑用户' : '查看用户') : '新增用户'" :busy="busy || resetting" :before-close="beforeClose" @update:model-value="emit('update:modelValue', $event)">
    <template #actions><el-button v-if="!editing" :icon="Connection" class="pms-form-drawer__reference" :disabled="busy" @click="oaVisible = true">引用 OA</el-button></template>
    <form id="pms-user-form" ref="formElement" @submit.prevent="save">
      <h3 class="pms-form-drawer__section">基本信息</h3>
      <PmsFormField v-slot="{ describedBy, invalid }" field-id="user-username" label="账号（工号）" required :error="errors.username">
        <PmsTextControl id="user-username" v-model="form.username" :aria-describedby="describedBy" :aria-invalid="invalid" aria-required="true" :disabled="editing || busy" :error="errors.username" maxlength="64" aria-label="账号（工号）" />
      </PmsFormField>
      <PmsFormField v-slot="{ describedBy, invalid }" field-id="user-real-name" label="员工姓名" required :error="errors.real_name">
        <PmsTextControl id="user-real-name" v-model="form.real_name" :aria-describedby="describedBy" :aria-invalid="invalid" aria-required="true" :disabled="busy || !canEdit" :error="errors.real_name" maxlength="64" aria-label="员工姓名" />
      </PmsFormField>
      <PmsFormField v-slot="{ describedBy, invalid }" field-id="user-email" label="邮箱" :error="errors.email">
        <PmsTextControl id="user-email" v-model="form.email" :aria-describedby="describedBy" :aria-invalid="invalid" :disabled="busy || !canEdit" :error="errors.email" maxlength="254" aria-label="邮箱" autocomplete="email" />
      </PmsFormField>
      <PmsFormField field-id="user-mobile" label="手机号"><PmsTextControl id="user-mobile" v-model="form.mobile" :disabled="busy || !canEdit" maxlength="20" aria-label="手机号" /></PmsFormField>
      <PmsFormField field-id="user-dept" label="部门">
        <PmsTreeSelectControl id="user-dept" :model-value="form.dept_id" :data="departments" :props="{ label: 'dept_name', value: 'id', children: 'children' }" :disabled="busy || !canEdit" clearable check-strictly aria-label="部门" @update:model-value="form.dept_id = $event == null || $event === '' ? null : Number($event)" />
      </PmsFormField>
      <h3 class="pms-form-drawer__section">访问权限</h3>
      <PmsFormField field-id="user-roles" label="角色">
        <PmsSelectControl id="user-roles" :model-value="form.role_ids" :options="roles" :disabled="busy || !canEdit" multiple aria-label="角色" placeholder="请选择角色" @update:model-value="form.role_ids = Array.isArray($event) ? $event.map(Number) : []" />
      </PmsFormField>
      <PmsFormField field-id="user-status" label="状态"><PmsSwitchControl id="user-status" :model-value="form.status === 1" :disabled="busy || !canEdit" aria-label="用户状态" @update:model-value="form.status = $event ? 1 : 0" /></PmsFormField>
      <p v-if="!editing" class="user-password-note">初始密码由参数设置提供，首次密码登录后需修改。</p>
    </form>
    <template #secondary><el-button v-if="editing && auth.hasPermission('system:user:reset-password')" :loading="resetting" :disabled="busy" @click="resetPassword">重置密码</el-button></template>
    <template #footer><el-button :disabled="busy || resetting" @click="close">取消</el-button><el-button v-if="canEdit" type="primary" :loading="busy" :disabled="resetting" native-type="submit" form="pms-user-form">{{ editing ? '保存' : '创建用户' }}</el-button></template>
  </PmsFormDrawer>
  <OaEmployeePicker v-model="oaVisible" @select="useEmployee" />
</template>

<style scoped>
.user-password-note { margin: 16px 0 0; color: var(--pms-text-secondary); font-size: var(--pms-font-size-base); line-height: 1.6; }
</style>
