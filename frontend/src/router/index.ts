import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'

const routes: RouteRecordRaw[] = [
  {
    path: '/login',
    name: 'Login',
    component: () => import('@/views/Login.vue'),
    meta: { title: '登录' },
  },
  {
    path: '/sso/login',
    name: 'SsoLogin',
    component: () => import('@/views/SsoLogin.vue'),
    meta: { title: 'OA 单点登录' },
  },
  {
    path: '/admin/token',
    name: 'TokenGenerator',
    component: () => import('@/views/TokenGenerator.vue'),
    meta: { title: 'SSO 链接生成器' },
  },
  {
    path: '/',
    component: () => import('@/layout/AppLayout.vue'),
    redirect: '/dashboard',
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '仪表盘' },
      },
      {
        path: 'system/user',
        name: 'UserList',
        component: () => import('@/views/system/UserList.vue'),
        meta: { title: '用户管理' },
      },
      {
        path: 'system/role',
        name: 'RoleList',
        component: () => import('@/views/system/RoleList.vue'),
        meta: { title: '角色管理' },
      },
      {
        path: 'system/menu',
        name: 'MenuList',
        component: () => import('@/views/system/MenuList.vue'),
        meta: { title: '菜单管理' },
      },
      {
        path: 'system/dept',
        name: 'DeptList',
        component: () => import('@/views/system/DeptList.vue'),
        meta: { title: '部门管理' },
      },
      {
        path: 'project/list',
        name: 'ProjectList',
        component: () => import('@/views/project/ProjectList.vue'),
        meta: { title: '项目列表' },
      },
      {
        path: 'project/:id/progress',
        name: 'ProjectProgress',
        component: () => import('@/views/project/ProjectProgress.vue'),
        meta: { title: '进度填报' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

/** 无需登录即可访问的路由 */
const PUBLIC_PATHS = ['/login', '/sso/login', '/admin/token']

// 路由守卫：未登录跳转到登录页
router.beforeEach((to, _from, next) => {
  const token = localStorage.getItem('access_token')
  if (!PUBLIC_PATHS.includes(to.path) && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
