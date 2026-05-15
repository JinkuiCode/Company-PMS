<template>
  <div class="sso-login">
    <div class="sso-card">
      <div class="sso-icon">
        <el-icon :size="48" :color="error ? '#F56C6C' : '#409EFF'">
          <Connection />
        </el-icon>
      </div>
      <h2 class="sso-title">{{ error ? '登录失败' : '正在通过 OA 统一认证登录...' }}</h2>
      <p v-if="error" class="sso-error">{{ error }}</p>
      <el-button v-if="error" type="primary" @click="retry">重新登录</el-button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { Connection } from '@element-plus/icons-vue'
import request from '@/utils/request'
import { useAuthStore } from '@/stores/auth'

const route = useRoute()
const router = useRouter()
const authStore = useAuthStore()

const error = ref('')

async function handleCallback() {
  const q = route.query

  try {
    // 调用后端 callback 端点，传递 OA 返回的所有参数
    const res: any = await request.get('/sso/callback', { params: q })

    localStorage.setItem('access_token', res.access_token)
    await authStore.fetchUser()
    router.replace({ name: 'Dashboard' })
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || 'OA 认证失败'
    error.value = detail
  }
}

function retry() {
  // 重新跳转到 OA 登录页
  window.location.href = '/api/sso/oa-redirect'
}

onMounted(() => { handleCallback() })
</script>

<style scoped>
.sso-login {
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
  min-width: 360px;
}
.sso-icon { margin-bottom: 20px; }
.sso-title { font-size: 20px; color: #303133; margin: 0 0 12px 0; }
.sso-error { color: #909399; margin-bottom: 20px; }
</style>
