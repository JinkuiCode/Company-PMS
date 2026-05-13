import request from '@/utils/request'

export interface LoginParams {
  username: string
  password: string
}

export interface TokenResult {
  access_token: string
  token_type: string
}

export interface UserInfo {
  id: number
  username: string
  real_name: string
  dept_id: number | null
  mobile: string | null
  status: number
}

export function login(params: LoginParams): Promise<TokenResult> {
  return request.post('/auth/login', params) as any
}

export function getUserInfo(): Promise<UserInfo> {
  return request.get('/auth/me') as any
}
