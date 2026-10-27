export function createAuthApi(request) {
  return {
    register: (body, signal) => request('/auth/register', { method: 'POST', body, signal, authRequired: false }),
    login: (body, signal) => request('/auth/login', { method: 'POST', body, signal, authRequired: false })
  }
}
