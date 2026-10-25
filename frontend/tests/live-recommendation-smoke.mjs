// Run against: python tests/serve-backend.py --port 8014 --recommendations
// Exercises real backend routes/SQLite and HTTP scoring transport; the local gateway's scores are fixtures.
import assert from 'node:assert/strict'
import { createApiClient } from '../src/api/request.js'
import { createRecommendApi } from '../src/api/recommend.js'
import { createProfileApi } from '../src/api/profile.js'
import { createRegistrationApi } from '../src/api/registrations.js'
import { createNotificationApi } from '../src/api/notifications.js'
import { useRecommendedActivities } from '../src/domain/recommendedActivities.js'
import { useProfile } from '../src/domain/profile.js'

const baseUrl = process.env.SMOKE_API_BASE_URL || 'http://127.0.0.1:8014/api'
const publicRequest = createApiClient({ baseUrl })
async function login(role, account) {
  const { token } = await publicRequest('/auth/login', { method: 'POST', authRequired: false, body: { role, account, password: 'smoke123' } })
  return createApiClient({ baseUrl, getToken: () => token })
}
const student = await login('student', 'S1')
const newStudent = await login('student', 'S2')
const organizer = await login('organizer', 'review')
const profileApi = createProfileApi(student)
const profile = useProfile(profileApi, () => 1)
await profile.load()
assert.equal(profile.loaded.value, true)
profile.edit()
profile.form.interests = '算法,竞赛,前端'
assert.equal(await profile.save(), true)
assert.equal(profile.profile.value.interests, '算法,竞赛,前端')
await assert.rejects(createProfileApi(student).getProfile(2), error => error.code === 403)
const blankProfile = useProfile(createProfileApi(newStudent), () => 2)
await blankProfile.load()
assert.equal(blankProfile.loaded.value, true)
assert.equal(blankProfile.form.major, '')
await assert.rejects(createRecommendApi(newStudent).score(), error => error.code === 400)
await assert.rejects(createRecommendApi(organizer).score(), error => error.code === 403)

const rec = createRecommendApi(student)
const scored = await rec.score()
assert.equal(scored.scored, 28)
assert.equal((await rec.list({})).total, 0)
const first = await rec.list({ match_major: 1, page: 1, page_size: 20 })
const second = await rec.list({ match_major: 1, page: 2, page_size: 20 })
assert.equal(first.items.length, 20)
assert.equal(second.items.length, 8)
assert.equal(first.total, 28)
assert.equal(new Set([...first.items, ...second.items].map(item => item.activity_id)).size, 28)
for (let i = 1; i < first.items.length; i++) assert.ok(first.items[i - 1].score >= first.items[i].score)
const cards = useRecommendedActivities(student)
await cards.load(first.items)
assert.equal(cards.error.value, '')
assert.deepEqual(cards.displayItems.value.map(item => item.activity.id), first.items.map(item => item.activity_id))
assert.deepEqual(cards.displayItems.value[0].reasons, first.items[0].reasons)
assert.match(first.items[0].reasons[0], /^专业匹配得分\d+(\.\d+)?\/10$/)
const reward = await rec.list({ need_conduct_score: 1 })
assert.equal(reward.total, 26) // Fixture uses 0.5 conduct points, interpreted by the gateway as eligible.
assert.ok(reward.items.every(item => item.reasons.length === 0)) // member-1: only matching dimensions produce reasons.
const noMatch = await rec.list({ need_innovation_score: 1 })
assert.equal(noMatch.total, 0)

const browse1 = await student('/activities', { query: { status: 'published,ongoing', page: 1, page_size: 20 } })
const browse2 = await student('/activities', { query: { status: 'published,ongoing', page: 2, page_size: 20 } })
assert.equal(browse1.total, 30)
assert.equal(browse2.items.length, 10)
assert.ok([...browse1.items, ...browse2.items].some(item => item.status === 'ongoing'))
assert.ok([...browse1.items, ...browse2.items].every(item => ['published', 'ongoing'].includes(item.status)))

const registrations = createRegistrationApi(student)
const id = first.items[0].activity_id
const detail = await registrations.getActivity(id)
assert.equal(detail.id, id)
const form = await registrations.getForm(id)
assert.ok(form.form_id)
const signup = await registrations.submitRegistration(id, { extra_fields: { team_extra: {}, members: [
  { role: 'captain', member_extra: { student_id: 'S1', name: '示例队长' } }
] } })
assert.ok((await registrations.getMyRegistrations(1)).items.some(item => item.registration_id === signup.registration_id))
const signupNotice = (await createNotificationApi(student).list()).items.find(item => item.activity_id === id)
assert.ok(signupNotice, 'signup must trigger a real internal HTTP notification')
assert.equal(signupNotice.type, '报名提醒')
assert.match(signupNotice.content, /成功报名/)
await registrations.cancelRegistration(signup.registration_id)

const notifications = createNotificationApi(student)
const notice = (await notifications.list()).items[0]
assert.ok(notice.content)
assert.equal((await notifications.markRead(notice.id)).is_read, 1)
assert.equal((await createNotificationApi(newStudent).list()).total, 0)

const saved = await profileApi.getProfile(1)
await profileApi.updateProfile(1, { ...saved, skills: 'force_gateway_error' })
await assert.rejects(rec.score(), error => error.code === 502)
await profileApi.updateProfile(1, saved)
assert.equal((await rec.score()).scored, 28)
console.log('PASS: real auth/profile (PUT then GET), empty-profile/role errors, score/list, filters/scored reasons/order/pagination, POD-1 batch cards, published+ongoing browse, detail → registration → real internal HTTP notification → cancellation, private notification list/read, scoring 502 and recovery. AI scores are local fixtures, not live LLM validation.')
