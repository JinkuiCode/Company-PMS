<template>
  <div class="dashboard">
    <h1>欢迎使用项目管理系统</h1>
    <p>您已登录，{{ authStore.user?.real_name }}</p>
    <el-button type="danger" @click="handleLogout">退出登录</el-button>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = useRouter()
const authStore = useAuthStore()

function handleLogout() {
  authStore.logout()
  router.push('/login')
}
</script>

<style scoped>
.dashboard {
  padding: 40px;
  text-align: center;
}
</style>
