import request from '@/utils/request'

export interface LoginParams {
  username: string
  password: string
  remember_me: boolean
}

export interface OaLoginParams {
  loginid: string
  password: string
  remember_me: boolean
}

export interface TokenResult {
  access_token: string
  token_type: string
  remember_token: string | null
}

export interface UserInfo {
  id: number
  username: string
  real_name: string
  dept_id: number | null
  mobile: string | null
  status: number
  role_codes: string[]
  permissions: string[]
  data_scope: number
  product_lines: string[] | null
}

export function login(params: LoginParams): Promise<TokenResult> {
  return request.post('/auth/login', params) as any
}

export function getUserInfo(): Promise<UserInfo> {
  return request.get('/auth/me') as any
}

/** PMS 账号密码登录（OA 菜单跳转入口） */
export function oaPasswordLogin(params: OaLoginParams): Promise<TokenResult> {
  return request.post('/sso/oa-password-login', params) as any
}

/** 免密令牌自动登录，返回新的 JWT */
export function autoLogin(rememberToken: string): Promise<TokenResult> {
  return request.post('/auth/auto-login', { remember_token: rememberToken }) as any
}

/** OA JSP 重定向过来的 SSO 免密登录 */
export function ssoLogin(ssoLoginId: string, ts: number, sign: string): Promise<TokenResult> {
  return request.post('/auth/sso-login', {
    sso_login_id: ssoLoginId,
    ts: ts,
    sign: sign,
  }) as any
}
