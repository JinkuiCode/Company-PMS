<template>
  <section class="forbidden-page">
    <div class="forbidden-code">403</div>
    <h1>无权访问此页面</h1>
    <p>当前角色没有该页面权限，权限调整后刷新或重新进入即可生效。</p>
    <el-button type="primary" size="small" @click="goToFirstAccessiblePage">返回可访问页面</el-button>
  </section>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

const destinations = [
  ['dashboard:view', '/dashboard'],
  ['project:archive:view', '/project/archive'],
  ['project:list:view', '/project/list'],
  ['system:user:view', '/system/user'],
  ['system:role:view', '/system/role'],
  ['system:dict:view', '/system/dict'],
  ['system:enum:view', '/system/enum'],
  ['system:operation-log:view', '/system/operation-log'],
] as const

function goToFirstAccessiblePage() {
  const destination = destinations.find(([permission]) => authStore.hasPermission(permission))
  router.push(destination?.[1] || '/login')
}
</script>

<style scoped>
.forbidden-page {
  min-height: calc(100vh - 88px);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: var(--pms-text);
  text-align: center;
}

.forbidden-code {
  color: var(--pms-primary);
  font-size: 56px;
  font-weight: 750;
  line-height: 1;
}

h1 {
  margin: 16px 0 8px;
  font-size: 20px;
}

p {
  margin: 0 0 20px;
  color: var(--pms-text-secondary);
  font-size: 13px;
}
</style>
