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
    path: '/sso/start',
    name: 'SsoStart',
    component: () => import('@/views/SsoStart.vue'),
    meta: { title: 'OA 统一认证' },
  },
  {
    path: '/sso/callback',
    name: 'SsoCallback',
    component: () => import('@/views/SsoCallback.vue'),
    meta: { title: 'OA 认证回调' },
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
        path: 'system/dict',
        name: 'DictList',
        component: () => import('@/views/system/MenuList.vue'),
        meta: { title: '数据字典' },
      },
      {
        path: 'system/field',
        name: 'FieldList',
        component: () => import('@/views/system/FieldList.vue'),
        meta: { title: '字段管理' },
      },
      {
        path: 'system/operation-log',
        name: 'OperationLogList',
        component: () => import('@/views/system/OperationLogList.vue'),
        meta: { title: '操作日志' },
      },
      {
        path: 'project/list',
        name: 'ProjectList',
        component: () => import('@/views/project/ProjectList.vue'),
        meta: { title: '项目进度' },
      },
      {
        path: 'project/archive',
        name: 'ProjectArchive',
        component: () => import('@/views/project/ProjectArchive.vue'),
        meta: { title: '项目档案' },
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
const PUBLIC_PATHS = ['/login', '/sso/login', '/sso/start', '/sso/callback', '/admin/token']

// 路由守卫：URL 参数 token 自动保存，未登录跳转到登录页
router.beforeEach((to, _from, next) => {
  // 处理 URL 参数中的 token（来自 SSO 登录页重定向）
  const urlToken = to.query.token as string
  if (urlToken) {
    localStorage.setItem('access_token', urlToken)
    // 清除 URL 中的 token 参数，跳转到首页
    next({ name: 'Dashboard', query: {} })
    return
  }

  const token = localStorage.getItem('access_token')
  if (!PUBLIC_PATHS.includes(to.path) && !token) {
    next('/login')
  } else {
    next()
  }
})

export default router
