export const tokenKey = 'lensbrief.token'
export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message) }
}
async function request(path: string, options: RequestInit = {}) {
  const headers = new Headers(options.headers)
  const token = sessionStorage.getItem(tokenKey)
  if (token) headers.set('Authorization', 'Bearer ' + token)
  if (typeof options.body === 'string') headers.set('Content-Type', 'application/json')
  const response = await fetch('/api' + path, { ...options, headers })
  if (!response.ok) {
    const data = await response.json().catch(() => null)
    const message = typeof data?.detail === 'string' ? data.detail
      : Array.isArray(data?.detail) ? data.detail.map((x: { msg: string }) => x.msg).join('，')
      : '请求失败，请重试。'
    if (response.status === 401 && token && path !== '/auth/login') {
      window.dispatchEvent(new Event('lensbrief:expired'))
    }
    throw new ApiError(response.status, message)
  }
  return response
}
export async function api<T>(path: string, options?: RequestInit): Promise<T> {
  const response = await request(path, options)
  return response.status === 204 ? undefined as T : await response.json() as T
}
export async function blob(path: string) {
  return (await request(path)).blob()
}
export function params(values: Record<string, string | number | null | undefined>) {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(values)) {
    if (value !== null && value !== undefined && value !== '') search.set(key, String(value))
  }
  return '?' + search.toString()
}
export const errorText = (error: unknown) => error instanceof Error ? error.message : '请求失败。'
