import { shallowRef } from 'vue'
import { api, tokenKey } from './api'
import type { Actor } from './types'

export const user = shallowRef<Actor | null>(null)
export async function signIn(username: string, password: string) {
  const result = await api<{ access_token: string; user: Actor }>('/auth/login', {
    method: 'POST', body: JSON.stringify({ username, password }),
  })
  sessionStorage.setItem(tokenKey, result.access_token)
  user.value = result.user
}
export function signOut() {
  sessionStorage.removeItem(tokenKey)
  user.value = null
}
export async function restoreUser() {
  if (!user.value && sessionStorage.getItem(tokenKey)) {
    try { user.value = await api<Actor>('/auth/me') } catch { signOut() }
  }
}
export function hasGrant(action: string) {
  return Boolean(user.value?.grants[action])
}
