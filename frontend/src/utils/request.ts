import axios from 'axios'
import { ElMessage } from 'element-plus'

const request = axios.create({
  baseURL: '/api',
  timeout: 15000,
})

// 请求拦截器：自动附带 token
request.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// 登录 API 路径（这些请求的 401 不应触发跳转）
const LOGIN_PATHS = ['/auth/login', '/sso/oa-password-login', '/auth/auto-login']

function formatErrorDetail(detail: unknown) {
  if (typeof detail === 'string' && detail.trim()) return detail
  if (Array.isArray(detail)) {
    const messages = detail.map(item => item?.msg).filter(Boolean)
    return messages.length ? messages.join('；') : '请求参数校验失败'
  }
  if (detail && typeof detail === 'object') {
    const structured = detail as {
      code?: string
      message?: string
      fields?: Array<{ field_key?: string; message?: string }>
    }
    if (structured.code === 'FIELD_POLICY_VALIDATION_FAILED' || structured.code === 'FIELD_POLICY_INVALID') {
      const fieldMessages = structured.fields
        ?.map(field => [field.field_key, field.message].filter(Boolean).join('：'))
        .filter(Boolean)
      if (fieldMessages?.length) return fieldMessages.join('；')
    }
    if (structured.message) return structured.message
  }
  return '请求失败，请稍后重试'
}

// 响应拦截器：统一错误处理
request.interceptors.response.use(
  (response) => response.data,
  (error) => {
    const detail = error.response?.data?.detail
    const msg = formatErrorDetail(detail)
    const requestUrl = error.config?.url || ''
    const isLoginRequest = LOGIN_PATHS.some(p => requestUrl.includes(p))

    if (error.response?.status === 401) {
      localStorage.removeItem('access_token')
      // 登录请求的 401 只提示错误，不跳转
      if (!isLoginRequest) {
        window.location.href = '/login'
      }
    }
    if (error.response?.status === 403 && !requestUrl.includes('/auth/me')) {
      window.dispatchEvent(new CustomEvent('pms:permission-denied'))
      import('@/stores/auth').then(({ useAuthStore }) => {
        useAuthStore().fetchUser().catch(() => undefined)
      })
    }
    // 非 401 或登录请求的 401：只弹消息，不跳转，让调用方自行处理
    if (isLoginRequest && error.response?.status === 401) {
      // 登录失败仅由调用方显示错误，这里不弹重复消息
      return Promise.reject(error)
    }
    ElMessage.error(msg)
    return Promise.reject(error)
  },
)

export default request
