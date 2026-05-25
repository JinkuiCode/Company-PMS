<template>
  <div class="sso-callback">
    <div class="callback-card">
      <div class="callback-icon">
        <el-icon :size="48" :color="error ? '#F56C6C' : '#409EFF'">
          <Connection />
        </el-icon>
      </div>

      <!-- 正在验证 OA 回调 -->
      <template v-if="verifying">
        <h2 class="callback-title">正在验证 OA 认证...</h2>
        <p class="callback-hint">请稍候，系统正在处理 OA 返回的认证信息</p>
      </template>

      <!-- 验证失败 -->
      <template v-else-if="error">
        <h2 class="callback-title" style="color:#F56C6C;">认证失败</h2>
        <p class="callback-error">{{ error }}</p>
        <el-button type="primary" @click="retryOA" style="margin-bottom:12px;">
          重新通过 OA 认证
        </el-button>
        <el-divider />
        <p class="callback-footnote">
          或使用
          <el-link type="primary" @click="goAccountLogin">账号密码登录</el-link>
        </p>
      </template>

      <!-- 验证成功（短暂显示后自动跳转） -->
      <template v-else>
        <h2 class="callback-title" style="color:#67C23A;">认证成功</h2>
        <p class="callback-hint">OA 认证通过，正在跳转到系统...</p>
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

const verifying = ref(true)
const error = ref('')

/** 处理 OA 回调：从 URL 提取参数 → 调用后端验证 → 存储 JWT → 跳转 */
async function handleCallback() {
  const q = route.query

  // 提取 OA 回调参数（处理多种可能的参数名）
  const ticket = q.ticket as string || q.token as string || ''
  const loginid = q.loginid as string || ''
  const username = q.username as string || ''

  if (!ticket && !loginid) {
    error.value = 'OA 回调缺少认证参数（ticket 或 loginid），请重新通过 OA 菜单访问'
    verifying.value = false
    return
  }

  try {
    const res: any = await request.get('/sso/callback', {
      params: { ticket, loginid, username, token: ticket },
    })

    if (res.access_token) {
      localStorage.setItem('access_token', res.access_token)
      try { localStorage.setItem('pms_token', res.access_token) } catch (_) { /* 兼容 oa-login-page */ }
      await authStore.fetchUser()

      // 短暂显示成功状态后跳转
      verifying.value = false
      setTimeout(() => {
        router.replace({ name: 'Dashboard' })
      }, 500)
    } else {
      error.value = 'OA 认证返回数据异常，缺少 access_token'
      verifying.value = false
    }
  } catch (e: any) {
    const detail = e?.response?.data?.detail || e?.message || 'OA 认证失败'
    error.value = typeof detail === 'string' ? detail : JSON.stringify(detail)
    verifying.value = false
  }
}

/** 重新走 OA CAS 认证流程 */
function retryOA() {
  window.location.href = '/api/sso/oa-redirect'
}

function goAccountLogin() {
  router.replace({ name: 'Login' })
}

onMounted(() => { handleCallback() })
</script>

<style scoped>
.sso-callback {
  height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  background: #f0f2f5;
}
.callback-card {
  background: #fff;
  border-radius: 8px;
  padding: 48px 40px;
  text-align: center;
  box-shadow: 0 2px 12px rgba(0,0,0,0.08);
  min-width: 380px;
  max-width: 420px;
}
.callback-icon { margin-bottom: 20px; }
.callback-title { font-size: 20px; color: #303133; margin: 0 0 12px 0; }
.callback-hint { color: #909399; margin-bottom: 20px; font-size: 14px; }
.callback-error { color: #F56C6C; margin-bottom: 16px; font-size: 14px; }
.callback-footnote { color: #b0b0b0; font-size: 13px; }
</style>
