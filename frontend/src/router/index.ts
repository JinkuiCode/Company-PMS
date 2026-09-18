import { createRouter, createWebHistory, type RouteRecordRaw } from 'vue-router'
import { useAuthStore } from '@/stores/auth'
import { rememberLoginDestination, consumeLoginDestination, chooseLoginDestination } from '@/utils/loginDestination'

const routes: RouteRecordRaw[] = [
  {
    path: '/change-password',
    name: 'ChangePassword',
    component: () => import('@/views/ChangePassword.vue'),
    meta: { title: '设置登录密码' },
  },
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
    meta: { title: 'SSO 链接生成器', permission: 'system:user:edit' },
  },
  {
    path: '/',
    component: () => import('@/layout/AppLayout.vue'),
    children: [
      {
        path: 'dashboard',
        name: 'Dashboard',
        component: () => import('@/views/Dashboard.vue'),
        meta: { title: '仪表盘', permission: 'dashboard:view' },
      },
      {
        path: 'system/user',
        name: 'UserList',
        component: () => import('@/views/system/UserList.vue'),
        meta: { title: '用户管理', permission: 'system:user:view' },
      },
      {
        path: 'system/role',
        name: 'RoleList',
        component: () => import('@/views/system/RoleList.vue'),
        meta: { title: '角色管理', permission: 'system:role:view' },
      },
      {
        path: 'system/parameter',
        name: 'ParameterList',
        component: () => import('@/views/system/ParameterList.vue'),
        meta: { title: '参数设置', permission: 'system:parameter:view' },
      },
      {
        path: 'system/dict',
        name: 'DictList',
        component: () => import('@/views/system/DataDictionaryList.vue'),
        meta: { title: '数据字典', permission: 'system:dict:view' },
      },
      {
        path: 'system/enum',
        name: 'EnumList',
        component: () => import('@/views/system/EnumList.vue'),
        meta: { title: '枚举管理', permission: 'system:enum:view' },
      },
      {
        path: 'system/field',
        redirect: '/system/enum',
      },
      {
        path: 'system/operation-log',
        name: 'OperationLogList',
        component: () => import('@/views/system/OperationLogList.vue'),
        meta: { title: '操作日志', permission: 'system:operation-log:view' },
      },
      {
        path: 'system/field-policy',
        name: 'FieldPolicyList',
        component: () => import('@/views/system/FieldPolicyList.vue'),
        meta: { title: '字段规则', permission: 'system:field-policy:view' },
      },
      {
        path: 'project/list',
        name: 'ProjectList',
        component: () => import('@/views/project/ProjectList.vue'),
        meta: { title: '项目进度', permission: 'project:list:view' },
      },
      {
        path: 'project/archive',
        name: 'ProjectArchive',
        component: () => import('@/views/project/ProjectArchive.vue'),
        meta: { title: '项目档案', permission: 'project:archive:view' },
      },
      {
        path: 'project/:id/progress',
        name: 'ProjectProgress',
        component: () => import('@/views/project/ProjectProgress.vue'),
        meta: { title: '进度填报', permission: 'project:list:view' },
      },
      {
        path: '403',
        name: 'Forbidden',
        component: () => import('@/views/Forbidden.vue'),
        meta: { title: '无权访问' },
      },
    ],
  },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

/** 无需登录即可访问的路由 */
const PUBLIC_PATHS = ['/login', '/sso/login', '/sso/start', '/sso/callback']

// 路由守卫：URL 参数 token 自动保存，未登录跳转到登录页
router.beforeEach(async (to) => {
  if (PUBLIC_PATHS.includes(to.path)) rememberLoginDestination(to.query.redirect)
  // 处理 URL 参数中的 token（来自 SSO 登录页重定向）
  const urlToken = to.query.token as string
  if (urlToken) {
    localStorage.setItem('access_token', urlToken)
    // 清除 URL 中的 token 参数，跳转到首页
    const query = { ...to.query }
    delete query.token
    rememberLoginDestination(router.resolve({ path: to.path, query }).fullPath)
    return { path: '/', query: {} }
  }

  const token = localStorage.getItem('access_token')
  if (!PUBLIC_PATHS.includes(to.path) && !token) {
    rememberLoginDestination(to.fullPath)
    return '/login'
  }

  if (!PUBLIC_PATHS.includes(to.path) && token) {
    const authStore = useAuthStore()
    try {
      await authStore.fetchUser()
    } catch {
      authStore.logout()
      rememberLoginDestination(to.fullPath)
      return '/login'
    }
    if (authStore.user?.must_change_password) {
      return to.path === '/change-password' ? true : '/change-password'
    }
    if (to.path === '/change-password') return '/'
    if (to.path === '/') {
      const canAccess = (path: string) => {
        const target = router.resolve(path)
        return target.matched.length > 0 && Boolean(target.meta.permission) && authStore.hasPermission(String(target.meta.permission))
      }
      return chooseLoginDestination(consumeLoginDestination(), authStore.user?.home_path, canAccess)
    }
    const permission = to.meta.permission as string | undefined
    if (permission && !authStore.hasPermission(permission)) {
      return '/403'
    }
  }
  return true
})

export default router
