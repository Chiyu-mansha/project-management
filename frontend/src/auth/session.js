import { readonly, shallowRef } from 'vue'

export function normalizeSession(value) {
  if (value == null) return null
  const role = typeof value.role === 'string' ? value.role.toLowerCase() : ''
  const id = Number(value.id)
  if (typeof value.token !== 'string' || !value.token.trim() ||
      !['student', 'organizer'].includes(role) || !Number.isSafeInteger(id) || id < 1) {
    throw new Error('登录信息无效，请重新登录')
  }
  return Object.freeze({ token: value.token, role, id })
}

// Login owns credentials. Keep one in-memory session across routes; never create a token here.
export function createSessionStore() {
  const current = shallowRef(null)
  return {
    session: readonly(current),
    setSession(value) { current.value = normalizeSession(value) },
    clearSession() { current.value = null }
  }
}

export const { session, setSession, clearSession } = createSessionStore()
