function userId(id) {
  if (id === undefined || id === null || String(id).trim() === '') throw new Error('缺少用户 ID')
  return encodeURIComponent(String(id))
}

export function createProfileApi(request) {
  return {
    getProfile: (id, signal) => request(`/users/${userId(id)}/profile`, { signal }),
    updateProfile: (id, body, signal) => request(`/users/${userId(id)}/profile`, { method: 'PUT', body, signal })
  }
}
