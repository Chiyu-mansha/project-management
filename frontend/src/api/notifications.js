function resourceId(id) {
  if (id === undefined || id === null || String(id).trim() === '') throw new Error('缺少资源 ID')
  return encodeURIComponent(String(id))
}

export function createNotificationApi(request) {
  return {
    list: (page = 1, pageSize = 20, signal) =>
      request('/notifications', {
        query: { page, page_size: pageSize },
        signal,
      }),
    unreadCount: (signal) =>
      request('/notifications/unread-count', { signal }),
    create: (body, signal) =>
      request('/notifications', { method: 'POST', body, signal }),
    markRead: (id, signal) =>
      request(`/notifications/${resourceId(id)}/read`, { method: 'PUT', signal }),
  }
}