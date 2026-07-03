<template>
  <el-container class="app-layout app-shell">
    <!-- 左侧菜单 -->
    <el-aside :width="isCollapse ? '64px' : '220px'" class="app-aside">
      <div class="logo">
        <span class="logo-mark">P</span>
        <span v-if="!isCollapse" class="logo-text">PMS 管理系统</span>
      </div>
      <el-menu
        :default-active="currentRoute"
        :collapse="isCollapse"
        :collapse-transition="false"
        router
        class="app-menu"
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
          <span class="header-title">{{ route.meta.title || '项目管理' }}</span>
        </div>
        <div class="header-right">
          <span class="user-name">{{ authStore.user?.real_name || authStore.user?.username || '当前用户' }}</span>
          <el-button type="danger" size="small" plain @click="handleLogout">退出</el-button>
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
import { Fold, Expand, Setting, User, Avatar, Menu, Folder, List, DataAnalysis, FolderOpened, Collection } from '@element-plus/icons-vue'
import { useAuthStore } from '@/stores/auth'
import request from '@/utils/request'

const Icons: Record<string, any> = { Setting, User, Avatar, Menu, Folder, List, DataAnalysis, FolderOpened, Collection }

const router = useRouter()
const route = useRoute()
const authStore = useAuthStore()
const currentRoute = computed(() => route.path)
const isCollapse = ref(false)
const menuTree = ref<any[]>([])

type MenuNode = {
  path?: string
  sort?: number
  children?: MenuNode[]
  [key: string]: any
}

function menuSortValue(menu: any) {
  if (menu.path === '/project/archive') return 0
  if (menu.path === '/project/list') return 1
  return Number(menu.sort ?? 99)
}

function normalizeMenus(menus: MenuNode[]): MenuNode[] {
  return [...menus]
    .map(menu => ({
      ...menu,
      children: menu.children?.length ? normalizeMenus(menu.children) : [],
    }))
    .sort((a, b) => menuSortValue(a) - menuSortValue(b))
}

async function fetchMenus() {
  const res = await request.get('/my-menus') as any
  menuTree.value = normalizeMenus(res || [])
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
  background: var(--pms-bg);
}

.app-aside {
  background: var(--pms-surface);
  border-right: 1px solid var(--pms-border-soft);
  overflow-y: auto;
  transition: width 180ms ease-out;
}
.app-aside::-webkit-scrollbar { width: 0; }

.logo {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: flex-start;
  gap: 10px;
  padding: 0 14px;
  color: var(--pms-text);
  border-bottom: 1px solid var(--pms-border-soft);
  white-space: nowrap;
  overflow: hidden;
}

.logo-mark {
  width: 32px;
  height: 32px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex: 0 0 auto;
  color: var(--pms-primary);
  background: var(--pms-primary-soft);
  border: 1px solid rgba(79, 70, 229, 0.18);
  border-radius: var(--pms-radius-sm);
  font-size: 14px;
  font-weight: 800;
}

.logo-text {
  min-width: 0;
  overflow: hidden;
  font-size: 15px;
  font-weight: 700;
  text-overflow: ellipsis;
}

.app-header {
  background: var(--pms-surface);
  display: flex;
  align-items: center;
  justify-content: space-between;
  border-bottom: 1px solid var(--pms-border-soft);
  padding: 0 18px;
  height: 56px;
}

.header-left {
  display: flex;
  align-items: center;
  gap: 12px;
}

.collapse-btn {
  color: var(--pms-text-secondary);
  cursor: pointer;
}
.collapse-btn:hover { color: var(--pms-primary); }

.header-title {
  color: var(--pms-text);
  font-size: 15px;
  font-weight: 650;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 12px;
}
.user-name {
  color: var(--pms-text-secondary);
  font-size: 13px;
}

.app-main {
  background: var(--pms-bg);
  padding: 16px;
  overflow-y: auto;
}

.menu-icon {
  font-size: 17px;
  vertical-align: middle;
}

:deep(.app-menu) {
  border-right: 0;
  padding: 8px;
  background: transparent;
}

:deep(.app-menu .el-menu-item),
:deep(.app-menu .el-sub-menu__title) {
  height: 40px;
  margin: 2px 0;
  padding-left: 12px !important;
  border-radius: var(--pms-radius-sm);
  color: var(--pms-text-secondary);
  font-size: 14px;
}

:deep(.app-menu .el-menu-item:hover),
:deep(.app-menu .el-sub-menu__title:hover) {
  color: var(--pms-text);
  background: var(--pms-surface-muted);
}

:deep(.app-menu .el-menu-item.is-active) {
  color: var(--pms-primary);
  background: var(--pms-primary-soft);
  font-weight: 700;
}

:deep(.app-menu .el-sub-menu.is-active > .el-sub-menu__title) {
  color: var(--pms-primary);
}

:deep(.app-menu.el-menu--collapse) {
  width: auto;
}

:deep(.app-menu.el-menu--collapse .el-menu-item),
:deep(.app-menu.el-menu--collapse .el-sub-menu__title) {
  justify-content: center;
  padding: 0 !important;
}
</style>
