<template>
  <div class="login-shell login-container">
    <div class="login-card">
      <div class="login-brand">PMS</div>
      <h1 class="login-title">项目管理系统</h1>
      <p class="login-subtitle">项目档案与进度协同管理</p>
      <el-form ref="formRef" :model="form" :rules="rules" size="large" @keyup.enter="handleLogin">
        <el-form-item prop="username">
          <el-input v-model="form.username" placeholder="请输入用户名" :prefix-icon="User" />
        </el-form-item>
        <el-form-item prop="password">
          <el-input
            v-model="form.password"
            type="password"
            placeholder="请输入密码"
            :prefix-icon="Lock"
            show-password
          />
        </el-form-item>
        <el-form-item>
          <el-button type="primary" :loading="loading" class="login-btn" @click="handleLogin">
            登录
          </el-button>
        </el-form-item>
      </el-form>
      <div class="login-footnote">
        <p class="login-hint">默认账号：admin / admin123</p>
        <p class="login-hint sso-hint">泛微 OA 用户请从 OA 门户进入</p>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, reactive } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage, type FormInstance, type FormRules } from 'element-plus'
import { User, Lock } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()
const formRef = ref<FormInstance>()
const loading = ref(false)

const form = reactive({
  username: 'admin',
  password: 'admin123',
})

const rules: FormRules = {
  username: [{ required: true, message: '请输入用户名', trigger: 'blur' }],
  password: [{ required: true, message: '请输入密码', trigger: 'blur' }],
}

async function handleLogin() {
  const valid = await formRef.value?.validate().catch(() => false)
  if (!valid) return

  loading.value = true
  try {
    await authStore.login(form.username, form.password)
    ElMessage.success('登录成功')
    router.push('/dashboard')
  } catch {
    // 错误已在 request 拦截器中处理
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.login-shell {
  width: 100vw;
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 24px;
  background: var(--pms-bg);
}

.login-card {
  width: min(100%, 392px);
  padding: 34px 34px 28px;
  background: var(--pms-surface);
  border: 1px solid var(--pms-border-soft);
  border-radius: var(--pms-radius);
  box-shadow: var(--pms-shadow-sm);
}

.login-brand {
  width: 42px;
  height: 42px;
  display: flex;
  align-items: center;
  justify-content: center;
  margin: 0 auto 18px;
  color: var(--pms-primary);
  background: var(--pms-primary-soft);
  border: 1px solid rgba(79, 70, 229, 0.18);
  border-radius: var(--pms-radius);
  font-size: 14px;
  font-weight: 800;
  letter-spacing: 0;
}

.login-title {
  margin: 0;
  font-size: 24px;
  font-weight: 700;
  line-height: 1.25;
  text-align: center;
  color: var(--pms-text);
}

.login-subtitle {
  margin: 8px 0 28px;
  text-align: center;
  font-size: 14px;
  color: var(--pms-text-secondary);
}

.login-btn {
  width: 100%;
  height: 42px;
}

.login-footnote {
  margin-top: 4px;
  padding-top: 14px;
  border-top: 1px solid var(--pms-border-soft);
}

.login-hint {
  margin: 0;
  text-align: center;
  font-size: 12px;
  color: var(--pms-text-muted);
}
.sso-hint {
  margin-top: 6px;
  color: var(--pms-text-secondary);
}

@media (max-width: 480px) {
  .login-card {
    padding: 28px 22px 24px;
  }
}
</style>
