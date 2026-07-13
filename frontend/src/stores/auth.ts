import { defineStore } from 'pinia'
import { ref } from 'vue'
import { login as loginApi, getUserInfo, autoLogin as autoLoginApi, type UserInfo } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string>(localStorage.getItem('access_token') || '')
  const user = ref<UserInfo | null>(null)

  async function login(username: string, password: string) {
    const res = await loginApi({ username, password, remember_me: false })
    token.value = res.access_token
    localStorage.setItem('access_token', res.access_token)
    await fetchUser()
  }

  /** 尝试用免密令牌自动登录，成功返回 true */
  async function tryAutoLogin(): Promise<boolean> {
    const rememberToken = localStorage.getItem('pms_remember_token')
    if (!rememberToken) return false
    try {
      const res = await autoLoginApi(rememberToken)
      token.value = res.access_token
      localStorage.setItem('access_token', res.access_token)
      // 滚动刷新：使用新令牌或保留旧令牌
      if (res.remember_token) {
        localStorage.setItem('pms_remember_token', res.remember_token)
      }
      await fetchUser()
      return true
    } catch {
      // 免密令牌失效，清理
      localStorage.removeItem('pms_remember_token')
      return false
    }
  }

  async function fetchUser() {
    user.value = await getUserInfo()
  }

  function hasPermission(permission: string) {
    return Boolean(user.value?.permissions?.includes(permission))
  }

  function hasAnyPermission(...permissions: string[]) {
    return permissions.some(hasPermission)
  }

  function logout() {
    token.value = ''
    user.value = null
    localStorage.removeItem('access_token')
    localStorage.removeItem('pms_remember_token')
  }

  return { token, user, login, tryAutoLogin, fetchUser, hasPermission, hasAnyPermission, logout }
})
