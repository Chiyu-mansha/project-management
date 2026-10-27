export function createCredentialApi(request) {
  return {
    checkin(activityId, channel = 'QR') {
      return request(`/activities/${activityId}/checkin`, { method: 'POST', body: { channel } })
    },
    checkinStatus(activityId) {
      return request(`/activities/${activityId}/checkin-status`)
    },
    checkinList(activityId) {
      return request(`/activities/${activityId}/checkin-list`)
    },
    confirm(activityId, credentialIds, note) {
      return request(`/activities/${activityId}/confirm`, {
        method: 'POST',
        body: { credential_ids: credentialIds, note },
      })
    },
    sign(credentialId, sealId = 'campus-default') {
      return request(`/credentials/${credentialId}/sign`, {
        method: 'POST',
        body: { seal_id: sealId },
      })
    },
    myCredentials(status) {
      return request('/credentials', { query: status ? { status } : {} })
    },
    exportCredentials(query = {}) {
      return request('/credentials/export', { query })
    },
    pdfUrl(credentialId) {
      return `/api/credentials/${credentialId}/pdf`
    },
  }
}
