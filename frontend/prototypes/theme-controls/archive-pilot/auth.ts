import { defineStore } from 'pinia'
import { ref } from 'vue'
import type { UserInfo } from '@/api/auth'
import { pilotUser } from './fixtures'

// A fixture identity, never a production login or browser credential.
export const useAuthStore=defineStore('auth',()=>{
  const user=ref<UserInfo|null>(pilotUser)
  const token=ref('')
  const hasPermission=(permission:string)=>Boolean(user.value?.permissions.includes(permission))
  const hasAnyPermission=(...permissions:string[])=>permissions.some(hasPermission)
  const fetchUser=async()=>{if(!user.value)user.value=pilotUser}
  const logout=()=>{user.value=null}
  const login=async()=>{throw Error('独立主题预览不接收登录凭据')}
  const tryAutoLogin=async()=>false
  return {user,token,hasPermission,hasAnyPermission,fetchUser,logout,login,tryAutoLogin}
})
