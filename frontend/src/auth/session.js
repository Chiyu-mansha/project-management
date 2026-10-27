import { readonly, shallowRef } from 'vue'

const STORAGE_KEY = 'pod2.session'

function getStorage() {
  // 测试(Node)环境没有 localStorage，返回 null
  return typeof localStorage !== 'undefined' ? localStorage : null
}

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

// 登录态存内存 + localStorage，刷新页面后仍保持登录；退出时清除
export function createSessionStore() {
  let initial = null
  try {
    const raw = getStorage()?.getItem(STORAGE_KEY)
    if (raw) initial = normalizeSession(JSON.parse(raw))
  } catch {}

  const current = shallowRef(initial)
  return {
    session: readonly(current),
    setSession(value) {
      current.value = normalizeSession(value)
      try { getStorage()?.setItem(STORAGE_KEY, JSON.stringify(current.value)) } catch {}
    },
    clearSession() {
      current.value = null
      try { getStorage()?.removeItem(STORAGE_KEY) } catch {}
    }
  }
}

export const { session, setSession, clearSession } = createSessionStore()
