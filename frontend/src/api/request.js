export class ApiError extends Error {
  constructor(message, code, status) {
    super(message)
    this.name = 'ApiError'
    this.code = code
    this.status = status
  }
}

// Authentication comes from the agreed login result; no storage convention is assumed.
export function createApiClient({ baseUrl = '/api', getToken = () => '', fetchImpl = globalThis.fetch, onUnauthorized } = {}) {
  return async function request(path, { method = 'GET', body, signal, query, allowBareResponse = false, authRequired = true } = {}) {
    const token = getToken()
    if (authRequired && !token) throw new ApiError('请先登录', 401)
    const search = new URLSearchParams()
    for (const [key, value] of Object.entries(query || {})) {
      if (value !== undefined && value !== null) search.set(key, String(value))
    }
    const url = `${baseUrl.replace(/\/$/, '')}${path}${search.size ? `?${search}` : ''}`
    let response
    try {
      response = await fetchImpl(url, {
        method,
        headers: {
          Accept: 'application/json',
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
          ...(body === undefined ? {} : { 'Content-Type': 'application/json' })
        },
        ...(body === undefined ? {} : { body: JSON.stringify(body) }),
        signal
      })
    } catch (error) {
      if (error.name === 'AbortError') throw error
      throw new ApiError('连接失败，请稍后重试')
    }
    let result
    try {
      result = await response.json()
    } catch {
      throw new ApiError('服务暂时不可用，请稍后重试', undefined, response.status)
    }
    if (getToken() !== token) throw new ApiError('登录状态已变更，请重新打开页面', 401)
    if (response.status === 401 || result?.code === 401) onUnauthorized?.()
    // Compatibility is opt-in for POD-1 activity reads only. Registration APIs stay strict.
    if (response.ok && allowBareResponse && result && typeof result === 'object' &&
        !Array.isArray(result) && !Object.hasOwn(result, 'code')) return result
    // 2026-10-11 final contract overrides the earlier code:200 / msg envelope.
    if (!response.ok || result?.code !== 0) {
      throw new ApiError(result?.message || '请求失败，请稍后重试', result?.code, response.status)
    }
    return result.data
  }
}
