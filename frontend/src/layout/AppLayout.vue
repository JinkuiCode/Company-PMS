<template>
  <el-container class="app-layout">
    <!-- 左侧菜单 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="app-aside">
      <div class="logo">
        <span v-if="!isCollapse">PMS 管理系统</span>
        <span v-else>PMS</span>
      </div>
      <el-menu
        :default-active="currentRoute"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
        background-color="#304156"
        text-color="#bfcbd9"
        active-text-color="#409EFF"
      >
        <template v-for="menu in menuTree" :key="menu.id">
          <!-- 有子菜单 -->
          <el-sub-menu v-if="menu.children.length > 0" :index="String(menu.id)">
            <template #title>
              <el-icon v-if="menu.icon" class="menu-icon"><component :is="Icons[menu.icon]" /></el-icon>
              <span>{{ menu.menu_name }}</span>
            </template>
            <el-menu-item
              v-for="child in menu.children"
              :key="child.id"
              :index="child.path"
            >
              <el-icon v-if="child.icon" class="menu-icon"><component :is="Icons[child.icon]" /></el-icon>
              <span>{{ child.menu_name }}</span>
            </el-menu-item>
          </el-sub-menu>
          <!-- 无子菜单 -->
          <el-menu-item v-else :index="menu.path">
            <el-icon v-if="menu.icon" class="menu-icon"><component :is="Icons[menu.icon]" /></el-icon>
            <span>{{ menu.menu_name }}</span>
          </el-menu-item>
        </template>
      </el-menu>
    </el-aside>

    <!-- 右侧内容 -->
    <el-container>
      <el-header class="app-header">
        <div class="header-left">
          <el-icon class="collapse-btn" @click="isCollapse = !isCollapse" :size="22">
            <Fold v-if="!isCollapse" /><Expand v-else />
          </el-icon>
        </div>
        <div class="header-right">
          <span class="user-name">{{ authStore.user?.real_name }}</span>
          <el-button type="danger" size="small" @click="handleLogout">退出</el-button>
        </div>
      </el-header>
      <el-main class="app-main">
        <router-view />
      </el-main>
    </el-container>
  </el-container>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { Fold, Expand, Setting, User, Avatar, Menu, OfficeBuilding, Folder, List, DataAnalysis } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import request from '@/utils/request'

const Icons: Record<string, any> = { Setting, User, Avatar, Menu, OfficeBuilding, Folder, List, DataAnalysis }

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const currentRoute = computed(() => route.path)
const isCollapse = ref(false)
const menuTree = ref<any[]>([])

async function fetchMenus() {
  const res = await request.get('/my-menus') as any
  menuTree.value = res || []
}

function handleLogout() {
  authStore.logout()
  router.push('/login')
}

onMounted(() => {
  fetchMenus()
  // 如果用户信息为空，先获取
  if (!authStore.user) {
    authStore.fetchUser()
  }
})
</script>

<style scoped>
.app-layout {
  height: 100vh;
}

.app-aside {
  background-color: #304156;
  overflow-y: auto;
  transition: width 0.3s;
}
.app-aside::-webkit-scrollbar { width: 0; }

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  font-size: 18px;
  font-weight: bold;
  border-bottom: 1px solid rgba(255,255,255,0.1);
  white-space: nowrap;
  overflow: hidden;
}

.app-header {
  background: #fff;
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid #e6e6e6;
  padding: 0 20px;
  height: 56px;
}

.collapse-btn { cursor: pointer; }
.collapse-btn:hover { color: #409EFF; }

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-name { color: #606266; }

.app-main {
  background: #f0f2f5;
  overflow-y: auto;
}

.menu-icon {
  font-size: 18px;
  vertical-align: middle;
}
</style>
