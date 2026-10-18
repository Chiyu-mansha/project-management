// Run ONLY against tests/serve-backend.py with a fresh disposable database.
import assert from 'node:assert/strict'
import { createApiClient } from '../src/api/request.js'
import { createRegistrationApi } from '../src/api/registrations.js'

const baseUrl = 'http://127.0.0.1:8012/api'
const SMOKE_PASSWORD = 'smoke123'
async function login(role, account) {
  const publicRequest = createApiClient({ baseUrl })
  const { token } = await publicRequest('/auth/login', { method: 'POST', body: { role, account, password: SMOKE_PASSWORD }, authRequired: false })
  return createRegistrationApi(createApiClient({ baseUrl, getToken: () => token }))
}
const owner = await login('organizer', 'review')
const captain = await login('student', 'S1')
const member = await login('student', 'S2')
const schema = {
  form_team_schema: [{ field_key: 'project_name', label: '项目名称', type: 'text', required: true }],
  form_member_schema: [
    { field_key: 'student_id', label: '学号', type: 'text', required: true },
    { field_key: 'name', label: '姓名', type: 'text', required: true }
  ]
}
const form = await owner.createForm(1, schema)
assert.ok(form.form_id)
await assert.rejects(owner.createForm(1, schema), error => error.status === 409)
assert.equal((await owner.updateForm(1, schema)).form_id, form.form_id)
assert.equal((await captain.getForm(1)).form_id, form.form_id)
assert.equal((await captain.getActivity(1)).id, 1) // Actual POD-1 bare response.
const payload = { extra_fields: { team_extra: { project_name: '联调回归项目' }, members: [
  { role: 'captain', member_extra: { student_id: 'S1', name: '示例队长' } },
  { role: 'member', member_extra: { student_id: 'S2', name: '示例队员' } }
] } }
const registration = await captain.submitRegistration(1, payload)
assert.ok(registration.registration_id)
await assert.rejects(captain.submitRegistration(1, payload), error => error.status === 409)
await assert.rejects(owner.updateForm(1, schema), error => error.status === 400)
assert.equal((await owner.getActivityRegistrations(1)).total, 1)
assert.equal((await captain.getMyRegistrations(1)).items[0].my_role, 'captain')
assert.equal((await member.getMyRegistrations(2)).items[0].my_role, 'member')
assert.equal((await member.getRegistration(registration.registration_id)).extra_fields.team_extra.project_name, '联调回归项目')
await assert.rejects(member.cancelRegistration(registration.registration_id), error => error.status === 403)
assert.equal(await captain.cancelRegistration(registration.registration_id), null)
assert.equal((await captain.getMyRegistrations(1)).total, 0)
assert.equal((await member.getMyRegistrations(2)).total, 0)
await assert.rejects(captain.getRegistration(registration.registration_id), error => error.status === 404)
for (const id of [2, 3]) {
  await owner.createForm(id, schema)
  await assert.rejects(captain.submitRegistration(id, payload), error => error.status === 400)
}
console.log('PASS: all 8 registration routes, POD-1 activity adapter, role restrictions, duplicate registration, template lock, cancellation and member cleanup, cancelled/deadline guards.')
