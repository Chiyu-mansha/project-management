export function registrationBlockReason(activity, now = Date.now()) {
  if (!activity) return '活动信息加载中'
  const messages = {
    draft: '活动尚未发布', ongoing: '活动已开始，不能报名',
    finished: '活动已结束', cancelled: '活动已取消'
  }
  if (activity.status !== 'published') return messages[activity.status] || '活动当前不可报名'
  if (activity.signup_deadline) {
    const value = String(activity.signup_deadline).trim().replace(' ', 'T')
    // Backend's date-only format means local midnight, not JavaScript's UTC date parsing.
    const deadline = Date.parse(/^\d{4}-\d{2}-\d{2}$/.test(value) ? `${value}T00:00:00` : value)
    if (!Number.isFinite(deadline)) return '报名截止时间异常，请联系发布者'
    if (now >= deadline) return '报名已截止'
  }
  return ''
}

export function ownsActivity(activity, session) {
  return session?.role?.toLowerCase() === 'organizer' && !!session.token &&
    activity?.organizer_id != null && String(activity.organizer_id) === String(session.id)
}
