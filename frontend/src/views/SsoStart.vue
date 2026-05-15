<template>
  <div class="sso-page">
    <div class="sso-card">
      <div class="sso-icon">
        <el-icon :size="48" color="#409EFF"><Connection /></el-icon>
      </div>
      <h2 class="sso-title">OA 统一认证登录</h2>
      <!-- 自动登录检测中 -->
      <p v-if="!autoLoginChecked" class="sso-hint" style="color:#E6A23C;">正在验证登录状态...</p>
      <template v-else>
      <p class="sso-hint">请输入您的 OA 工号，系统将自动验证身份</p>

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
            placeholder="请输入 OA 工号"
            :prefix-icon="User"
            size="large"
            clearable
          />
        </el-form-item>
        <el-form-item>
          <el-button
            type="primary"
            size="large"
            :loading="loading"
            @click="handleLogin"
            style="width: 100%"
          >
            {{ loading ? '正在验证...' : '统一认证登录' }}
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
import { User, Connection } from '@element-plus/icons-vue'
import type { FormInstance, FormRules } from 'element-plus'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const formRef = ref<FormInstance>()
const loading = ref(false)
const error = ref('')
const autoLoginChecked = ref(false) // 自动登录检测是否完成

const form = reactive({ loginid: '' })
const rules: FormRules = {
  loginid: [{ required: true, message: '请输入 OA 工号', trigger: 'blur' }],
}

// 页面加载时尝试自动登录（用 fetch 避免 request 拦截器的 401 跳转）
onMounted(async () => {
  const token = localStorage.getItem('access_token')
  if (!token) {
    autoLoginChecked.value = true
    return
  }

  try {
    const resp = await fetch('/api/auth/me', {
      headers: { Authorization: `Bearer ${token}` },
    })
    if (resp.ok) {
      const res = await resp.json()
      if (res && res.username) {
        // token 有效，直接跳转到仪表盘
        authStore.user = res
        router.replace({ name: 'Dashboard' })
        return
      }
    }
  } catch {
    // 网络错误，忽略
  }
  // token 无效或网络错误，清除并显示表单
  localStorage.removeItem('access_token')
  autoLoginChecked.value = true
})

async function handleLogin() {
  if (!formRef.value) return

  const valid = await formRef.value.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  error.value = ''

  try {
    const res: any = await request.post('/sso/oa-login', {
      loginid: form.loginid,
    })

    localStorage.setItem('access_token', res.access_token)
    await authStore.fetchUser()
    router.replace({ name: 'Dashboard' })
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'OA 认证失败'
  } finally {
    loading.value = false
  }
}

function goAccountLogin() {
  router.replace({ name: 'Login' })
}
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
.sso-hint { color: #909399; margin-bottom: 28px; font-size: 14px; }
.sso-error { color: #F56C6C; margin-top: 12px; font-size: 13px; }
.sso-footnote { color: #b0b0b0; font-size: 13px; }
</style>
