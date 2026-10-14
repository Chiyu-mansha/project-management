import { validateDetailView, validateTemplate } from './model.js'

// Matches backend/registrations.py:get_registration on the POD-2 merge branch.
export function readRegistrationDetail(data) {
  if (!data?.form || !data.extra_fields || typeof data.extra_fields !== 'object') {
    throw new Error('报名详情加载失败，请稍后重试')
  }
  const form = validateTemplate(data.form)
  return validateDetailView({
    teamSchema: form.form_team_schema,
    memberSchema: form.form_member_schema,
    teamExtra: data.extra_fields.team_extra,
    members: data.extra_fields.members,
    isIndividual: form.min_team_member === 1 && form.max_team_member === 1
  })
}
