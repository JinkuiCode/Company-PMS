const PENDING_KEY = 'pms_login_destination'

export function safeBusinessPath(value: unknown): string | null {
  if (typeof value !== 'string' || !/^\/(project|system)\/[a-z0-9/-]+(?:[?#].*)?$/.test(value) && value !== '/dashboard') return null
  if (/[\\\s]/.test(value)) return null
  const url = new URL(value, 'https://pms.invalid')
  if (['token', 'sign', 'code', 'password'].some(key => url.searchParams.has(key))) return null
  return value
}

export function rememberLoginDestination(value: unknown) {
  const path = safeBusinessPath(value)
  if (path) sessionStorage.setItem(PENDING_KEY, path)
}

export function consumeLoginDestination() {
  const path = sessionStorage.getItem(PENDING_KEY)
  sessionStorage.removeItem(PENDING_KEY)
  return safeBusinessPath(path)
}

export function chooseLoginDestination(requested: unknown, home: unknown, canAccess: (path: string) => boolean) {
  for (const value of [requested, home]) {
    const path = safeBusinessPath(value)
    if (path && canAccess(path)) return path
  }
  return '/403'
}
