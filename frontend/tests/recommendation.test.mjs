import test from 'node:test'
import assert from 'node:assert/strict'
import { useRecommendations, readRecommendations } from '../src/domain/recommendations.js'
import { useRecommendedActivities } from '../src/domain/recommendedActivities.js'
import { useProfile } from '../src/domain/profile.js'
import { createApiClient } from '../src/api/request.js'
import { createRecommendApi } from '../src/api/recommend.js'
import { createProfileApi } from '../src/api/profile.js'

const deferred = () => { let resolve, reject; const promise = new Promise((yes, no) => { resolve = yes; reject = no }); return { promise, resolve, reject } }
const result = id => ({ items: [{ activity_id: id, reasons: ['专业匹配'] }], total: 1 })
const activity = (id, status = 'published') => ({ id, title: `活动${id}`, status, signup_deadline: '2099-12-31T23:59:59' })
const storedProfile = { major: '计算机', grade: '2024', interests: '编程', skills: 'Python', need_conduct_score: 1, need_innovation_score: 0, need_comprehensive_score: 1 }

test('推荐和画像 API 保持约定方法、路径、六个筛选和七个画像字段', async () => {
  const calls = []
  const request = createApiClient({ getToken: () => 'student:1', fetchImpl: async (url, init) => {
    calls.push({ url, ...init }); return new Response(JSON.stringify({ code: 0, data: {} }))
  } })
  const api = createRecommendApi(request)
  await api.score()
  await api.list({ match_major: 1, match_interests: 0, match_skills: 0, need_conduct_score: 1, need_innovation_score: 0, need_comprehensive_score: 1, page: 2, page_size: 20 })
  await createProfileApi(request).updateProfile(1, storedProfile)
  assert.equal(calls[0].url, '/api/recommend/score')
  assert.equal(calls[0].method, 'POST')
  assert.equal(calls[0].body, undefined)
  const query = new URL(calls[1].url, 'http://test').searchParams
  assert.equal(query.get('match_major'), '1')
  assert.equal(query.get('need_comprehensive_score'), '1')
  assert.equal(query.get('page'), '2')
  assert.equal(query.size, 8)
  assert.equal(calls[2].url, '/api/users/1/profile')
  assert.equal(calls[2].method, 'PUT')
  assert.deepEqual(JSON.parse(calls[2].body), storedProfile)
})

test('进入时评分，未选择标签保持空白；评分期间切换标签使用完成时的选择', async () => {
  const gate = deferred(), calls = []
  const state = useRecommendations({ score: () => gate.promise, list: async query => { calls.push(query); return result(2) } }, () => true)
  const scoring = state.score()
  assert.equal(state.scoring.value, true)
  state.tags.match_major = true
  await state.load()
  state.tags.match_major = false
  state.tags.need_conduct_score = true
  gate.resolve({ scored: 1 })
  await scoring
  assert.equal(calls.length, 1)
  assert.equal(calls[0].match_major, 0)
  assert.equal(calls[0].need_conduct_score, 1)
  state.reset()
  await state.load()
  assert.deepEqual(state.items.value, [])
  assert.equal(calls.length, 1)
})

test('全取消标签后，旧请求即使未成功中断也不能填回卡片', async () => {
  const gate = deferred()
  const state = useRecommendations({ list: () => gate.promise }, () => true)
  state.tags.match_major = true
  const old = state.load()
  state.tags.match_major = false
  await state.load()
  gate.resolve(result(1))
  await old
  assert.deepEqual(state.items.value, [])
  assert.equal(state.total.value, 0)
  assert.equal(state.loading.value, false)
})

test('快速筛选与会话重置忽略过期响应，分页传给服务端', async () => {
  const old = deferred(), calls = []
  const state = useRecommendations({ list: async query => { calls.push(query); return calls.length === 1 ? old.promise : result(2) } }, () => true)
  state.tags.match_major = true
  const pending = state.load()
  state.tags.match_interests = true
  await state.load(2)
  assert.equal(calls[1].page, 2)
  assert.equal(calls[1].page_size, 20)
  old.resolve(result(1))
  await pending
  assert.equal(state.items.value[0].activity_id, 2)
  state.reset()
  assert.deepEqual(state.items.value, [])
  assert.equal(state.hasFilter.value, false)
})

test('空画像与评分失败可见且可重试，不制造评分；列表错误可恢复', async () => {
  let fail = true
  const state = useRecommendations({
    score: async () => { if (fail) throw Object.assign(new Error('请先完善画像'), { code: 400 }) },
    list: async () => { if (fail) throw new Error('网络失败'); return result(3) }
  }, () => true)
  await state.score()
  assert.equal(state.needsProfile.value, true)
  assert.equal(state.scoreError.value, '请先完善画像')
  state.tags.match_skills = true
  await state.load()
  assert.equal(state.listError.value, '网络失败')
  fail = false
  await state.score()
  assert.equal(state.scoreError.value, '')
  assert.equal(state.listError.value, '')
  assert.equal(state.items.value[0].activity_id, 3)
  assert.throws(() => readRecommendations({ items: [{ activity_id: 1 }], total: 1 }))
})

test('批量取活动后保持推荐顺序和理由，隐藏已取消、过期及缺失活动', async () => {
  const calls = []
  const expired = { ...activity(4), signup_deadline: '2000-01-01T00:00:00' }
  const state = useRecommendedActivities(async (path, options) => {
    calls.push({ path, ...options })
    return { items: [activity(1), activity(2), activity(3, 'cancelled'), expired], total: 4 }
  })
  const items = [2, 1, 3, 4, 5].map(id => ({ activity_id: id, reasons: [`理由${id}`] }))
  await state.load(items)
  assert.equal(calls.length, 1)
  assert.equal(calls[0].path, '/activities')
  assert.equal(calls[0].query.ids, '2,1,3,4,5')
  assert.deepEqual(state.displayItems.value.map(item => item.activity.id), [2, 1])
  assert.deepEqual(state.displayItems.value[0].reasons, ['理由2'])
  assert.equal(state.unavailable.value, 3)
})

test('卡片查询失败显示错误且可重试；旧批量查询不覆盖新列表', async () => {
  const gate = deferred()
  let calls = 0
  const state = useRecommendedActivities(async () => {
    if (++calls === 1) return gate.promise
    if (calls === 2) throw new Error('批量查询失败')
    return { items: [activity(2)], total: 1 }
  })
  const old = state.load(result(1).items)
  await state.load(result(2).items)
  assert.equal(state.error.value, '批量查询失败')
  await state.load(result(2).items)
  gate.resolve({ items: [activity(1)], total: 1 })
  await old
  assert.equal(state.displayItems.value[0].activity.id, 2)
  assert.equal(state.error.value, '')
  state.clear()
  assert.deepEqual(state.displayItems.value, [])
})

test('新账户 NULL 画像可查看编辑，保存后再次 GET 返回权威数据', async () => {
  let gets = 0, saved
  const state = useProfile({
    getProfile: async () => ++gets === 1 ? Object.fromEntries(Object.keys(storedProfile).map(key => [key, null])) : storedProfile,
    updateProfile: async (id, body) => { saved = body }
  }, () => 1)
  await state.load()
  assert.equal(state.editing.value, false)
  assert.equal(state.loaded.value, true)
  state.edit()
  Object.assign(state.form, storedProfile)
  assert.equal(await state.save(), true)
  assert.deepEqual(saved, storedProfile)
  assert.equal(gets, 2)
  assert.equal(state.editing.value, false)
  assert.deepEqual(state.profile.value, storedProfile)
})

test('画像首次读取失败禁止空白覆盖；保存失败保留草稿', async () => {
  let failLoad = true
  const state = useProfile({
    getProfile: async () => { if (failLoad) throw new Error('读取失败'); return storedProfile },
    updateProfile: async () => { throw new Error('保存失败') }
  }, () => 1)
  await state.load()
  state.edit()
  assert.equal(state.editing.value, false)
  assert.equal(await state.save(), false)
  failLoad = false
  await state.load()
  state.edit()
  state.form.major = '软件工程'
  assert.equal(await state.save(), false)
  assert.equal(state.editing.value, true)
  assert.equal(state.form.major, '软件工程')
  assert.equal(state.profile.value.major, '计算机')
})

test('画像写入成功但刷新失败明确提示，重载只 GET；会话变化丢弃旧结果', async () => {
  let gets = 0, writes = 0
  const state = useProfile({
    getProfile: async () => { if (++gets === 2) throw new Error('服务暂时不可用'); return storedProfile },
    updateProfile: async () => { ++writes }
  }, () => 1)
  await state.load()
  state.edit()
  await state.save()
  assert.match(state.error.value, /已保存.*重新加载失败/)
  assert.equal(state.editing.value, false)
  assert.equal(state.loaded.value, false)
  await state.load()
  assert.equal(writes, 1)
  const gate = deferred()
  const slow = useProfile({ getProfile: () => gate.promise }, () => 1)
  const old = slow.load()
  slow.reset()
  gate.resolve(storedProfile)
  await old
  assert.equal(slow.loaded.value, false)
  assert.equal(slow.form.major, '')
})
