<template>
  <div class="sso-page">
    <div class="sso-card">
      <div class="sso-icon">
        <el-icon :size="48" color="#409EFF"><Connection /></el-icon>
      </div>
      <h2 class="sso-title">OA 统一认证登录</h2>

      <!-- 自动登录检测中 -->
      <template v-if="checking">
        <p class="sso-hint" style="color:#E6A23C;">正在验证登录状态...</p>
      </template>

      <!-- 登录表单 -->
      <template v-else>
        <p class="sso-hint">请输入您的 <strong>OA 工号和 OA 密码</strong>验证身份</p>
        <p class="sso-sub-hint">注意：此处使用 OA 系统密码，非 PMS 密码</p>

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
              placeholder="OA 工号"
              :prefix-icon="User"
              size="large"
              clearable
            />
          </el-form-item>
          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              placeholder="OA 密码"
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
              {{ loading ? '正在验证...' : 'OA 统一认证登录' }}
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
import { useRouter } from 'vue-router'
import { User, Lock, Connection } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import { oaPasswordLogin } from '@/api/auth'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const error = ref('')
const checking = ref(true)

const form = reactive({
  loginid: '',
  password: '',
  rememberMe: true,
})

const rules: FormRules = {
  loginid: [{ required: true, message: '请输入 OA 工号', trigger: 'blur' }],
  password: [{ required: true, message: '请输入 OA 密码', trigger: 'blur' }],
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
  // 免密令牌失效，清理
  localStorage.removeItem('pms_remember_token')
  return false
}

/** 自动登录：先验证 JWT，JWT 过期则用免密令牌换取新 JWT */
async function autoLogin(): Promise<boolean> {
  // 第一步：检查 localStorage 中的 JWT 是否仍有效
  const token = localStorage.getItem('access_token')
  if (token) {
    const jwtValid = await verifyJwt(token)
    if (jwtValid) {
      await authStore.fetchUser()
      router.replace({ name: 'Dashboard' })
      return true
    }
    // JWT 失效，清理
    localStorage.removeItem('access_token')
  }

  // 第二步：尝试用免密令牌换取新 JWT
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

    // 保存 JWT 和免密令牌到 localStorage（同源 port 5174，不受 iframe 分区影响）
    localStorage.setItem('access_token', res.access_token)
    if (res.remember_token) {
      localStorage.setItem('pms_remember_token', res.remember_token)
    }

    await authStore.fetchUser()
    router.replace({ name: 'Dashboard' })
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || '认证失败，请检查工号和密码'
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
  background: #f0f2f5;
}
.sso-card {
  background: #fff;
  border-radius: 8px;
  padding: 48px 40px;
  text-align: center;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  min-width: 380px;
  max-width: 420px;
}
.sso-icon { margin-bottom: 20px; }
.sso-title { font-size: 20px; color: #303133; margin: 0 0 8px 0; }
.sso-hint { color: #909399; margin-bottom: 8px; font-size: 14px; }
.sso-sub-hint { color: #c0c4cc; margin-bottom: 20px; font-size: 12px; }
.sso-error { color: #F56C6C; margin-top: 12px; font-size: 13px; }
.sso-footnote { color: #b0b0b0; font-size: 13px; }
</style>
