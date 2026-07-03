<template>
  <div class="sso-page">
    <div class="sso-card">
      <div class="sso-icon">
        <el-icon :size="40"><Connection /></el-icon>
      </div>
      <h2 class="sso-title">PMS 项目管理系统</h2>

      <!-- SSO 自动登录中 / 验证登录状态中 -->
      <template v-if="checking">
        <p class="sso-hint sso-checking">{{ checkingMsg }}</p>
      </template>

      <!-- 登录表单（SSO 失败或无 SSO 参数时显示） -->
      <template v-else>
        <p class="sso-hint">请输入您的 <strong>PMS 账号和密码</strong></p>

        <el-form
          ref="formRef"
          :model="form"
          :rules="rules"
          label-width="0"
          @submit.prevent="handleLogin"
        >
          <el-form-item prop="loginid">
            <el-input
              v-model="form.loginid"
              placeholder="PMS 账号"
              :prefix-icon="User"
              size="large"
              clearable
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="PMS 密码"
              :prefix-icon="Lock"
              size="large"
              show-password
              @keyup.enter="handleLogin"
            />
          </el-form-item>
          <el-form-item>
            <el-checkbox v-model="form.rememberMe" size="small">
              记住我（半年内免密登录）
            </el-checkbox>
          </el-form-item>
          <el-form-item>
            <el-button
              type="primary"
              size="large"
              :loading="loading"
              @click="handleLogin"
              style="width: 100%"
            >
              {{ loading ? '正在验证...' : '登录 PMS' }}
            </el-button>
          </el-form-item>
        </el-form>

        <p v-if="error" class="sso-error">{{ error }}</p>
        <el-divider />
        <p class="sso-footnote">
          也可使用
          <el-link type="primary" @click="goAccountLogin">账号密码登录</el-link>
        </p>
      </template>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { User, Lock, Connection } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { oaPasswordLogin, ssoLogin } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const error = ref('')
const checking = ref(true)
const checkingMsg = ref('正在验证登录状态...')

const form = reactive({
  loginid: '',
  password: '',
  rememberMe: true,
})

const rules: FormRules = {
  loginid: [{ required: true, message: '请输入 PMS 账号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入 PMS 密码', trigger: 'blur' }],
}

/** 通道0：OA JSP 重定向过来的 SSO 免密登录（最高优先级） */
async function tryOaSsoLogin(): Promise<boolean> {
  const ssoLoginId = route.query.sso_login_id as string
  const ts = route.query.ts as string
  const sign = route.query.sign as string

  if (!ssoLoginId || !ts || !sign) return false

  checkingMsg.value = 'OA 单点登录验证中...'

  try {
    const res = await ssoLogin(ssoLoginId, Number(ts), sign)
    localStorage.setItem('access_token', res.access_token)
    if (res.remember_token) {
      localStorage.setItem('pms_remember_token', res.remember_token)
    }
    await authStore.fetchUser()
    // 清除 URL 中的 SSO 参数，防止重复用过期参数请求
    router.replace({ name: 'Dashboard', query: {} })
    return true
  } catch (e: any) {
    const detail = e?.response?.data?.detail || 'OA 认证失败'
    error.value = detail
    return false
  }
}

/** 用原始 fetch 验证 JWT 是否有效（绕过 axios 401 拦截器的强制跳转） */
async function verifyJwt(token: string): Promise<boolean> {
  try {
    const resp = await fetch('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (resp.ok) {
      const data = await resp.json()
      if (data && data.username) return true
    }
  } catch { /* 网络错误 */ }
  return false
}

/** 用原始 fetch 调用免密自动登录（绕过 axios 拦截器） */
async function tryAutoLoginWithFetch(): Promise<boolean> {
  const rememberToken = localStorage.getItem('pms_remember_token')
  if (!rememberToken) return false

  try {
    const resp = await fetch('/api/auth/auto-login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ remember_token: rememberToken }),
    })
    if (resp.ok) {
      const data = await resp.json()
      if (data.access_token) {
        localStorage.setItem('access_token', data.access_token)
        if (data.remember_token) {
          localStorage.setItem('pms_remember_token', data.remember_token)
        }
        await authStore.fetchUser()
        return true
      }
    }
  } catch { /* 网络错误 */ }
  localStorage.removeItem('pms_remember_token')
  return false
}

/** 自动登录：OA SSO → JWT → 免密令牌 */
async function autoLogin(): Promise<boolean> {
  // 通道0：OA JSP 重定向过来的 SSO 免密登录（最高优先级，每次进入都尝试）
  const oaOk = await tryOaSsoLogin()
  if (oaOk) return true

  // 通道1：检查 localStorage 中的 JWT 是否仍有效
  const token = localStorage.getItem('access_token')
  if (token) {
    const jwtValid = await verifyJwt(token)
    if (jwtValid) {
      await authStore.fetchUser()
      router.replace({ name: 'Dashboard' })
      return true
    }
    localStorage.removeItem('access_token')
  }

  // 通道2：尝试用免密令牌换取新 JWT
  const ok = await tryAutoLoginWithFetch()
  if (ok) {
    router.replace({ name: 'Dashboard' })
    return true
  }

  return false
}

async function handleLogin() {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  error.value = ''

  try {
    const res = await oaPasswordLogin({
      loginid: form.loginid,
      password: form.password,
      remember_me: form.rememberMe,
    })
    localStorage.setItem('access_token', res.access_token)
    if (res.remember_token) {
      localStorage.setItem('pms_remember_token', res.remember_token)
    }
    await authStore.fetchUser()
    router.replace({ name: 'Dashboard' })
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '认证失败，请检查账号和密码'
    error.value = detail
  } finally {
    loading.value = false
  }
}

function goAccountLogin() {
  router.replace({ name: 'Login' })
}

onMounted(async () => {
  const ok = await autoLogin()
  if (ok) return
  checking.value = false
})
</script>

<style scoped>
.sso-page {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: var(--pms-bg);
}
.sso-card {
  width: min(100%, 400px);
  background: var(--pms-surface);
  border: 1px solid var(--pms-border-soft);
  border-radius: var(--pms-radius);
  padding: 36px 34px 30px;
  text-align: center;
  box-shadow: var(--pms-shadow-sm);
}
.sso-icon {
  width: 52px;
  height: 52px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 18px;
  color: var(--pms-primary);
  background: var(--pms-primary-soft);
  border: 1px solid rgba(79, 70, 229, 0.18);
  border-radius: var(--pms-radius);
}
.sso-title {
  margin: 0 0 10px;
  color: var(--pms-text);
  font-size: 20px;
  font-weight: 700;
}
.sso-hint {
  margin: 0 0 18px;
  color: var(--pms-text-secondary);
  font-size: 14px;
  line-height: 1.6;
}
.sso-checking {
  color: var(--pms-warning);
}
.sso-error {
  margin-top: 12px;
  color: var(--pms-danger);
  font-size: 13px;
}
.sso-footnote {
  margin: 0;
  color: var(--pms-text-muted);
  font-size: 13px;
}
</style>
