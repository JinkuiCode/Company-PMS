<template>
  <div class="sso-login">
    <div class="sso-card">
      <div class="sso-icon">
        <el-icon :size="48" color="#409EFF"><Connection /></el-icon>
      </div>
      <h2 v-if="loading" class="sso-title">正在验证 OA 登录...</h2>
      <template v-else-if="error">
        <h2 class="sso-title" style="color:#F56C6C;">登录失败</h2>
        <p class="sso-error">{{ error }}</p>
        <el-button type="primary" @click="goLogin">返回登录页</el-button>
      </template>
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

const loading = ref(true)
const error = ref('')

async function doSSO() {
  const q = route.query

  try {
    let res: any

    if (q.token) {
      // 方式1: AES 加密 token（泛微 synthirdlogin 方式）
      res = await request.post('/sso/verify', { token: q.token as string })
    } else if (q.loginid && q.ts && q.sign) {
      // 方式2: HMAC 签名 URL 参数
      res = await request.get('/sso/url/verify', { params: {
        loginid: q.loginid, username: q.username || q.loginid,
        dept: q.dept || '', ts: q.ts, sign: q.sign,
      } }) as any
    } else if (q.loginid) {
      // 方式3: OA 菜单直接登录（仅 loginid，后端通过 Referer 校验）
      res = await request.post('/sso/oa-login', {
        loginid: q.loginid,
        username: (q.username as string) || (q.loginid as string),
        dept: (q.dept as string) || '',
      })
    } else {
      error.value = '缺少 SSO 认证参数（token 或 loginid）'
      loading.value = false
      return
    }

    localStorage.setItem('access_token', res.access_token)
    await authStore.fetchUser()
    router.replace({ name: 'Dashboard' })
  } catch (e: any) {
    error.value = e?.response?.data?.detail || e?.message || 'SSO 验证失败'
    loading.value = false
  }
}

function goLogin() {
  router.replace({ name: 'Login' })
}

onMounted(() => { doSSO() })
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
