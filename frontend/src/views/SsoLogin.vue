<template>
  <div class="sso-login">
    <div class="sso-card">
      <div class="sso-icon">
        <el-icon :size="40"><Connection /></el-icon>
      </div>
      <h2 v-if="loading" class="sso-title">正在验证 OA 登录...</h2>
      <template v-else-if="error">
        <h2 class="sso-title is-error">登录失败</h2>
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
  padding: 24px;
  background: var(--pms-bg);
}
.sso-card {
  width: min(100%, 380px);
  background: var(--pms-surface);
  border: 1px solid var(--pms-border-soft);
  border-radius: var(--pms-radius);
  padding: 38px 34px;
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
  margin: 0 0 12px;
  color: var(--pms-text);
  font-size: 20px;
  font-weight: 700;
}
.sso-title.is-error {
  color: var(--pms-danger);
}
.sso-error {
  margin: 0 0 20px;
  color: var(--pms-text-secondary);
  font-size: 13px;
  line-height: 1.6;
}
</style>
