import test from 'node:test'
import assert from 'node:assert/strict'
import { createApiClient } from '../src/api/request.js'
import { createRegistrationApi } from '../src/api/registrations.js'
import { createSessionStore } from '../src/auth/session.js'
import { ownsActivity, registrationBlockReason } from '../src/domain/activityAccess.js'

const activity = { id: 7, organizer_id: 10, status: 'published', signup_deadline: '2026-10-18T12:00:00+08:00' }
const now = Date.parse('2026-10-18T11:59:59+08:00')
const student = { token: 'test-only', role: 'STUDENT', id: '100' }

test('one validated login session is shared across routes and cleared on logout', () => {
  const store = createSessionStore()
  store.setSession(student)
  assert.deepEqual(store.session.value, { token: 'test-only', role: 'student', id: 100 })
  for (const invalid of [{ ...student, token: '' }, { ...student, role: 'admin' }, { ...student, id: 0 }]) {
    assert.throws(() => store.setSession(invalid), /登录信息无效/)
    assert.equal(store.session.value.id, 100)
  }
  store.clearSession()
  assert.equal(store.session.value, null)
})

test('organizer controls belong to the activity owner only', () => {
  assert.equal(ownsActivity(activity, { token: 'test', role: 'organizer', id: '10' }), true)
  for (const session of [null, { token: 'test', role: 'student', id: 10 }, { token: 'test', role: 'organizer', id: 11 }]) {
    assert.equal(ownsActivity(activity, session), false)
  }
})

test('registration respects all five states and the exact signup deadline', () => {
  assert.equal(registrationBlockReason(activity, now), '')
  assert.match(registrationBlockReason(activity, now + 1000), /已截止/)
  for (const status of ['draft', 'ongoing', 'finished', 'cancelled', 'unknown']) {
    assert.ok(registrationBlockReason({ ...activity, status }, now))
  }
  assert.match(registrationBlockReason({ ...activity, signup_deadline: 'invalid' }, now), /时间异常/)
  assert.equal(registrationBlockReason({ ...activity, signup_deadline: null }, now), '')
  assert.equal(registrationBlockReason({ ...activity, signup_deadline: '2026-10-18 12:00:00' }, new Date(2026, 9, 18, 11, 59, 59).getTime()), '')
  assert.match(registrationBlockReason({ ...activity, signup_deadline: '2026-10-18' }, new Date(2026, 9, 18, 0, 0, 0).getTime()), /已截止/)
})

test('only the POD-1 activity adapter accepts legacy bare JSON and the standard envelope', async () => {
  for (const result of [activity, { code: 0, data: activity }]) {
    const api = createRegistrationApi(createApiClient({ getToken: () => 'token', fetchImpl: async () => new Response(JSON.stringify(result)) }))
    assert.deepEqual(await api.getActivity(7), activity)
    if (!Object.hasOwn(result, 'code')) await assert.rejects(api.getForm(7))
  }
  for (const [status, result] of [[404, { message: '活动不存在' }], [200, { code: 409, message: '活动异常' }]]) {
    const api = createRegistrationApi(createApiClient({ getToken: () => 'token', fetchImpl: async () => new Response(JSON.stringify(result), { status }) }))
    await assert.rejects(api.getActivity(7))
  }
})

test('public activity/dev token reads do not invent Authorization credentials', async () => {
  let options
  const request = createApiClient({ fetchImpl: async (_, value) => { options = value; return new Response('{"code":0,"data":{}}') } })
  await request('/dev/token', { method: 'POST', body: { role: 'student', id: 100 }, authRequired: false })
  assert.equal(options.headers.Authorization, undefined)
  await assert.rejects(request('/users/100/registrations'), error => error.code === 401)
})

test('401 notifies login owner, but a late response cannot log out a newer session', async () => {
  let expired = 0
  const request = createApiClient({ getToken: () => 'same', onUnauthorized: () => ++expired, fetchImpl: async () => new Response('{"code":401,"message":"登录过期"}', { status: 401 }) })
  await assert.rejects(request('/users/100/registrations'), /登录过期/)
  assert.equal(expired, 1)
  let token = 'old'
  const lateRequest = createApiClient({ getToken: () => token, onUnauthorized: () => ++expired, fetchImpl: async () => { token = 'new'; return new Response('{"code":401}', { status: 401 }) } })
  await assert.rejects(lateRequest('/users/100/registrations'), /登录状态已变更/)
  assert.equal(expired, 1)
})
