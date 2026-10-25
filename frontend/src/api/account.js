export function createAccountApi(request) {
  return {
    me: (signal) => request('/account/me', { signal }),
    list: (signal) => request('/account/list', { signal }),
    updateBasic: (body, signal) => request('/account/basic', { method: 'PUT', body, signal }),
    changePassword: (body, signal) => request('/account/password', { method: 'POST', body, signal }),
    updateAvatar: (url, signal) => request('/account/avatar', { method: 'POST', body: { url }, signal }),
    switchAccount: (body, signal) => request('/account/switch', { method: 'POST', body, signal })
  }
}
