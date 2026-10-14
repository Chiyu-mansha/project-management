function resourceId(id) {
  if (id === undefined || id === null || String(id).trim() === '') throw new Error('缺少资源 ID')
  return encodeURIComponent(String(id))
}

export function createNotificationApi(request) {
  return {
    list: (userId, page = 1, pageSize = 20, signal) =>
      request('/notifications', {
        query: { user_id: userId, page, page_size: pageSize },
        signal,
      }),
    create: (body, signal) =>
      request('/notifications', { method: 'POST', body, signal }),
    markRead: (id, signal) =>
      request(`/notifications/${resourceId(id)}/read`, { method: 'PUT', signal }),
  }
}