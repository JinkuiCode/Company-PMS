<script setup lang="ts">
import { nextTick, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { PmsFormField, PmsTextControl } from '@/form-system'
import { changePassword } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const auth = useAuthStore()
const password = ref('')
const confirmation = ref('')
const error = ref('')
const confirmationError = ref('')
const formElement = ref<HTMLFormElement>()
const busy = ref(false)
async function focusFirstInvalid() {
  await nextTick()
  formElement.value?.querySelector<HTMLElement>('[aria-invalid="true"]:not(:disabled)')?.focus()
}
async function save() {
  if (busy.value) return
  error.value = ''
  confirmationError.value = ''
  if ([...password.value].length < 8 || [...password.value].length > 64) error.value = '新密码须为 8–64 个字符'
  if (!confirmation.value || password.value !== confirmation.value) confirmationError.value = '两次输入的密码不一致'
  if (error.value || confirmationError.value) { await focusFirstInvalid(); return }
  busy.value = true
  try {
    const result = await changePassword({ new_password: password.value, confirm_password: confirmation.value })
    localStorage.setItem('access_token', result.access_token)
    localStorage.removeItem('pms_remember_token')
    auth.token = result.access_token
    password.value = ''; confirmation.value = ''
    await auth.fetchUser()
    ElMessage.success('密码已修改')
    await router.replace('/')
  } catch (e: any) { error.value = typeof e.response?.data?.detail === 'string' ? e.response.data.detail : '修改失败，请检查输入后重试' }
  finally { busy.value = false; await focusFirstInvalid() }
}
function exit() { auth.logout(); void router.replace('/login') }
</script>

<template>
  <main class="password-change-page">
    <form ref="formElement" class="password-change-form" @submit.prevent="save">
      <h1>设置登录密码</h1>
      <p>首次登录或密码重置后，需设置个人密码才能继续。</p>
      <PmsFormField v-slot="{ describedBy, invalid }" field-id="new-password" label="新密码" required hint="8–64 个字符，无需定期修改。请勿使用初始密码、账号或常见弱密码。" :error="error">
        <PmsTextControl id="new-password" v-model="password" :aria-describedby="describedBy" :aria-invalid="invalid" aria-required="true" type="password" autocomplete="new-password" :disabled="busy" :error="error" aria-label="新密码" />
      </PmsFormField>
      <PmsFormField v-slot="{ describedBy, invalid }" field-id="confirm-password" label="确认新密码" required :error="confirmationError">
        <PmsTextControl id="confirm-password" v-model="confirmation" :aria-describedby="describedBy" :aria-invalid="invalid" aria-required="true" type="password" autocomplete="new-password" :disabled="busy" :error="confirmationError" aria-label="确认新密码" />
      </PmsFormField>
      <div class="password-change-actions"><el-button :disabled="busy" @click="exit">退出登录</el-button><el-button native-type="submit" type="primary" :loading="busy">保存并继续</el-button></div>
    </form>
  </main>
</template>

<style scoped>
.password-change-page { min-height: 100dvh; display: grid; place-items: center; padding: 24px; background: var(--pms-bg); box-sizing: border-box; }
.password-change-form { width: 100%; max-width: 420px; display: grid; gap: 20px; padding: 28px; border: 1px solid var(--pms-border); border-radius: var(--pms-radius); background: var(--pms-surface); box-sizing: border-box; }
h1 { font-size: 20px; margin: 0; color: var(--pms-text); }
p { font-size: var(--pms-font-size-base); color: var(--pms-text-muted); margin: 0; }
.password-change-actions { display: flex; justify-content: flex-end; gap: 8px; }
</style>
