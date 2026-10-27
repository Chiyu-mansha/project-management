function resourceId(id) {
  if (id === undefined || id === null || String(id).trim() === '') throw new Error('缺少资源 ID')
  return encodeURIComponent(String(id))
}

export function createRegistrationApi(request) {
  const activityPath = (id) => `/activities/${resourceId(id)}`
  const registrationPath = (id) => `/registrations/${resourceId(id)}`
  return {
    createForm: (id, body, signal) => request(`${activityPath(id)}/forms`, { method: 'POST', body, signal }),
    getForm: (id, signal) => request(`${activityPath(id)}/forms`, { signal }),
    updateForm: (id, body, signal) => request(`${activityPath(id)}/forms`, { method: 'PUT', body, signal }),
    getActivityRegistrations: (id, page = 1, pageSize = 20, signal) => request(`${activityPath(id)}/registrations`, {
      query: { page, page_size: pageSize }, signal
    }),
    submitRegistration: (id, body, signal) => request(`${activityPath(id)}/registrations`, { method: 'POST', body, signal }),
    getMyRegistrations: (id, page = 1, pageSize = 20, signal) => request(`/users/${resourceId(id)}/registrations`, {
      query: { page, page_size: pageSize }, signal
    }),
    getRegistration: (id, signal) => request(registrationPath(id), { signal }),
    cancelRegistration: (id, signal) => request(registrationPath(id), { method: 'DELETE', signal }),
    // Read-only POD-1 endpoint, explicitly documented in the final contract.
    getActivity: (id, signal) => request(activityPath(id), { signal, allowBareResponse: true })
  }
}
