import test from 'node:test'
import assert from 'node:assert/strict'
import { createApiClient } from '../src/api/request.js'
import { createRegistrationApi } from '../src/api/registrations.js'
import { readRegistrationDetail } from '../src/domain/adapters.js'
import { generateFieldKey } from '../src/domain/fieldKeys.js'
import {
  buildFormPayload, buildRegistrationPayload, createRegistrationDraft,
  createTemplateDraft, FIXED_MEMBER_FIELDS, newMember, newQuestion, readList, validateTemplate
} from '../src/domain/model.js'

function template(overrides = {}) {
  return {
    form_id: 1,
    form_team_schema: [{ field_key: 'project_name', label: '项目名称', type: 'text', required: true }],
    form_member_schema: FIXED_MEMBER_FIELDS.map((field) => ({ ...field })),
    min_team_member: 2, max_team_member: 4, ...overrides
  }
}
function completeDraft(form = template()) {
  const draft = createRegistrationDraft(form)
  draft.teamAnswers.project_name = '项目'
  draft.members.forEach((member, index) => Object.assign(member.answers, { student_id: `202300${index + 1}`, name: `同学${index + 1}` }))
  return draft
}
function response(data, { code = 0, status = 200, message } = {}) {
  return new Response(JSON.stringify({ code, data, ...(message ? { message } : {}) }), { status })
}

test('最新统一壳只接受 code 0，并从每次当前会话读取 Bearer token', async () => {
  const calls = []
  let token = 'first-token'
  const request = createApiClient({ getToken: () => token, fetchImpl: async (...args) => { calls.push(args); return response({ form_id: 1 }) } })
  assert.deepEqual(await request('/activities/1/forms'), { form_id: 1 })
  token = 'second-token'
  await request('/activities/2/forms')
  assert.equal(calls[0][1].headers.Authorization, 'Bearer first-token')
  assert.equal(calls[1][1].headers.Authorization, 'Bearer second-token')
  const obsolete = createApiClient({ getToken: () => 'token', fetchImpl: async () => response({}, { code: 200 }) })
  await assert.rejects(obsolete('/activities/1/forms'))
})

test('未登录不发出请求', async () => {
  let sent = false
  const request = createApiClient({ fetchImpl: async () => { sent = true } })
  await assert.rejects(request('/users/1/registrations'), (error) => error.code === 401)
  assert.equal(sent, false)
})

test('POD-1 活动详情兼容实际裸 JSON 和将来的统一壳，报名接口仍严格验壳', async () => {
  const activity = { id: 7, status: 'published', min_team_member: 2, max_team_member: 4 }
  for (const body of [activity, { code: 0, data: activity }]) {
    const api = createRegistrationApi(createApiClient({
      getToken: () => 'token',
      fetchImpl: async () => new Response(JSON.stringify(body), { status: 200 })
    }))
    assert.deepEqual(await api.getActivity(7), activity)
  }
  const api = createRegistrationApi(createApiClient({
    getToken: () => 'token', fetchImpl: async () => new Response(JSON.stringify(activity), { status: 200 })
  }))
  await assert.rejects(api.getForm(7), /请求失败/)
})

test('活动详情裸响应适配不能绕过 HTTP 错误或业务错误', async () => {
  for (const [body, status] of [[{ message: '活动不存在' }, 404], [{ code: 403, message: '无权限访问' }, 200]]) {
    const api = createRegistrationApi(createApiClient({
      getToken: () => 'token',
      fetchImpl: async () => new Response(JSON.stringify(body), { status })
    }))
    await assert.rejects(api.getActivity(7), (error) => error.message === body.message)
  }
})

test('请求期间登录状态变化时不向新会话返回旧会话结果', async () => {
  let token = 'old-token'
  const request = createApiClient({
    getToken: () => token,
    fetchImpl: async () => { token = 'new-token'; return response({ privateResult: 'old-session' }) }
  })
  await assert.rejects(request('/users/100/registrations'), (error) => error.code === 401)
})

test('HTTP 与业务错误保留 message；拒绝取消时保留线下处理原因', async () => {
  for (const status of [200, 400, 403, 409, 500]) {
    const request = createApiClient({ getToken: () => 'token', fetchImpl: async () => response(null, { code: 409, status, message: '已发凭证，请线下处理' }) })
    await assert.rejects(request('/registrations/1', { method: 'DELETE' }), (error) => error.message === '已发凭证，请线下处理' && error.code === 409)
  }
})

test('8 个报名接口的方法、路径、JSON 与分页参数按文档发送', async () => {
  const calls = []
  const request = createApiClient({ getToken: () => 'token', fetchImpl: async (...args) => { calls.push(args); return response({}) } })
  const api = createRegistrationApi(request)
  const formBody = { form_team_schema: [], form_member_schema: FIXED_MEMBER_FIELDS }
  const body = { extra_fields: { team_extra: {}, members: [] } }
  await api.createForm(7, formBody)
  await api.getForm(7)
  await api.updateForm(7, formBody)
  await api.getActivityRegistrations(7, 2, 20)
  await api.submitRegistration(7, body)
  await api.getMyRegistrations(100)
  await api.getRegistration(3)
  await api.cancelRegistration(3)
  assert.deepEqual(calls.map(([url, options]) => [url, options.method]), [
    ['/api/activities/7/forms', 'POST'], ['/api/activities/7/forms', 'GET'], ['/api/activities/7/forms', 'PUT'],
    ['/api/activities/7/registrations?page=2&page_size=20', 'GET'], ['/api/activities/7/registrations', 'POST'],
    ['/api/users/100/registrations?page=1&page_size=20', 'GET'], ['/api/registrations/3', 'GET'], ['/api/registrations/3', 'DELETE']
  ])
  assert.deepEqual(JSON.parse(calls[0][1].body), formBody)
  assert.deepEqual(JSON.parse(calls[4][1].body), body)
  assert.equal(calls[7][1].body, undefined)
})

test('缺少资源 ID 不发请求', async () => {
  const api = createRegistrationApi(() => assert.fail('不应发请求'))
  assert.throws(() => api.getForm(undefined), /ID/)
  assert.throws(() => api.getRegistration(''), /ID/)
})

test('报名详情直接使用已实现后端的 form/extra_fields，无需外部适配函数', async () => {
  const form = template()
  const extra = buildRegistrationPayload(form, completeDraft(form)).extra_fields
  const data = {
    registration_id: 3, activity_id: 7, form_id: 1,
    activity_name: '软件创新大赛', activity_status: 'published',
    registered_at: '2026-10-01T14:00:00', my_role: 'captain',
    form, extra_fields: extra
  }
  const api = createRegistrationApi(createApiClient({ getToken: () => 'token', fetchImpl: async () => response(data) }))
  const detail = readRegistrationDetail(await api.getRegistration(3))
  assert.deepEqual(detail.teamExtra, { project_name: '项目' })
  assert.equal(detail.teamSchema[0].label, '项目名称')
  assert.equal(detail.members[1].member_extra.student_id, '2023002')
  assert.equal(detail.isIndividual, false)
  data.form = { ...form, min_team_member: 1, max_team_member: 1 }
  data.extra_fields = { team_extra: extra.team_extra, members: [extra.members[0]] }
  assert.equal(readRegistrationDetail(data).isIndividual, true)
})

test('报名详情响应不完整时显示错误，不补造 schema、成员或人数', () => {
  const data = { form: template(), extra_fields: { team_extra: {}, members: [{ role: 'captain', member_extra: {} }] } }
  for (const broken of [null, {}, { ...data, form: null }, { ...data, extra_fields: {} },
    { ...data, form: { ...data.form, min_team_member: undefined } },
    { ...data, extra_fields: { ...data.extra_fields, members: [] } }]) {
    assert.throws(() => readRegistrationDetail(broken), /加载失败/)
  }
})

test('新建模板无预设队伍题目；只有两个固定队员字段', async () => {
  const draft = createTemplateDraft()
  const payload = await buildFormPayload(draft)
  assert.deepEqual(payload, { form_team_schema: [], form_member_schema: FIXED_MEMBER_FIELDS })
  assert.equal(JSON.stringify(payload).includes('_uiId'), false)
})

test('不传生成器也能保存拼音题目；已有 key 在改题干后保留', async () => {
  const draft = createTemplateDraft()
  const field = newQuestion()
  field.label = '项目名称'
  draft.form_team_schema.push(field)
  const generated = await buildFormPayload(draft)
  assert.equal(generated.form_team_schema[0].field_key, 'xiang_mu_ming_cheng')
  field.field_key = ''
  let count = 0
  const payload = await buildFormPayload(draft, async (label) => { ++count; assert.equal(label, '项目名称'); return 'project_name' })
  assert.equal(payload.form_team_schema[0].field_key, 'project_name')
  field.label = '项目标题'
  await buildFormPayload(draft, () => assert.fail('已有 key 不重建'))
  assert.equal(count, 1)
})

test('拼音 key 无声调，保留英文数字，ü 使用 v；空题干和纯标点给出提示', async () => {
  assert.equal(await generateFieldKey('联系电话'), 'lian_xi_dian_hua')
  assert.equal(await generateFieldKey('Team Name 2026'), 'team_name_2026')
  assert.equal(await generateFieldKey('女生'), 'nv_sheng')
  assert.equal(await generateFieldKey('2026'), 'field_2026')
  await assert.rejects(generateFieldKey('  '), /题干不能为空/)
  await assert.rejects(generateFieldKey('？！'), /至少包含/)
})

test('重复或同音题目自动防重；保留后面的已有 key；两个 schema 独立', async () => {
  const draft = createTemplateDraft()
  draft.form_team_schema = ['联系方式', '联系方式'].map((label) => ({ ...newQuestion(), label }))
  draft.form_team_schema.push({ field_key: 'lian_xi_fang_shi', label: '原联系方式', type: 'text', required: false })
  draft.form_member_schema.push({ ...newQuestion(), label: '联系方式' })
  const payload = await buildFormPayload(draft)
  assert.deepEqual(payload.form_team_schema.map((field) => field.field_key), ['lian_xi_fang_shi_2', 'lian_xi_fang_shi_3', 'lian_xi_fang_shi'])
  assert.equal(payload.form_member_schema.at(-1).field_key, 'lian_xi_fang_shi')
  assert.deepEqual(await buildFormPayload(draft), payload)
  const member = createTemplateDraft()
  member.form_member_schema.unshift({ ...newQuestion(), label: 'name' })
  assert.equal((await buildFormPayload(member)).form_member_schema[0].field_key, 'name_2')
})

test('模板题干不能为空，同一 schema key 唯一；两个 schema 互不干扰', async () => {
  const empty = createTemplateDraft(template())
  empty.form_team_schema[0].label = ' '
  await assert.rejects(buildFormPayload(empty), /题干不能为空/)
  const duplicates = createTemplateDraft(template())
  duplicates.form_team_schema.push({ ...duplicates.form_team_schema[0] })
  await assert.rejects(buildFormPayload(duplicates), /重复/)
  const separate = createTemplateDraft(template())
  separate.form_team_schema[0].field_key = 'name'
  await buildFormPayload(separate)
})

test('固定学号姓名不能缺失、改名、改类型或解除必填', async () => {
  for (const modify of [
    (draft) => draft.form_member_schema.splice(0, 1),
    (draft) => { draft.form_member_schema[0].label = '邮箱' },
    (draft) => { draft.form_member_schema[0].type = 'textarea' },
    (draft) => { draft.form_member_schema[0].required = false }
  ]) {
    const draft = createTemplateDraft()
    modify(draft)
    await assert.rejects(buildFormPayload(draft))
  }
})

test('报名按最低人数初始化；每张卡片的答案独立', () => {
  const draft = createRegistrationDraft(template())
  assert.equal(draft.members.length, 2)
  assert.deepEqual(draft.members.map((member) => member.role), ['captain', 'member'])
  draft.members[0].answers.name = '队长'
  assert.equal(draft.members[1].answers.name, '')
  assert.notEqual(draft.members[0]._uiId, draft.members[1]._uiId)
})

test('报名仅提交 schema 答案，保留原始文本；不发送 form_id、user_id、UI key', () => {
  const form = template()
  const draft = completeDraft(form)
  draft.teamAnswers.project_name = '  项目\n介绍  '
  draft.teamAnswers.unrelated = '不应发送'
  draft.members[0].answers.unrelated = '不应发送'
  const payload = buildRegistrationPayload(form, draft)
  assert.deepEqual(Object.keys(payload), ['extra_fields'])
  assert.deepEqual(payload.extra_fields.team_extra, { project_name: '  项目\n介绍  ' })
  assert.deepEqual(payload.extra_fields.members[0], { role: 'captain', member_extra: { student_id: '2023001', name: '同学1' } })
  assert.equal(JSON.stringify(payload).includes('_uiId'), false)
  assert.equal(JSON.stringify(payload).includes('unrelated'), false)
})

test('必填题和每张队员卡片校验；没有硬编码示例题目', () => {
  const form = template({ form_member_schema: [...FIXED_MEMBER_FIELDS, { field_key: 'intro', label: '个人介绍', type: 'textarea', required: true }] })
  const draft = completeDraft(form)
  assert.throws(() => buildRegistrationPayload(form, draft), /个人介绍/)
  draft.members.forEach((member) => { member.answers.intro = '介绍' })
  buildRegistrationPayload(form, draft)
  draft.teamAnswers.project_name = ' '
  assert.throws(() => buildRegistrationPayload(form, draft), /项目名称/)
})

test('拒绝重复学号、删除队长和越界人数', () => {
  const form = template()
  const duplicate = completeDraft(form)
  duplicate.members[1].answers.student_id = duplicate.members[0].answers.student_id
  assert.throws(() => buildRegistrationPayload(form, duplicate), /重复学号/)
  const missingCaptain = completeDraft(form)
  missingCaptain.members[0].role = 'member'
  assert.throws(() => buildRegistrationPayload(form, missingCaptain), /队长/)
  const tooFew = completeDraft(form)
  tooFew.members.pop()
  assert.throws(() => buildRegistrationPayload(form, tooFew), /人数/)
  const tooMany = completeDraft(form)
  while (tooMany.members.length <= form.max_team_member) tooMany.members.push(newMember(form.form_member_schema))
  assert.throws(() => buildRegistrationPayload(form, tooMany), /人数/)
})

test('单人活动提交仍使用 captain，但只初始化一张卡片', () => {
  const form = template({ form_team_schema: [], min_team_member: 1, max_team_member: 1 })
  const draft = completeDraft(form)
  const payload = buildRegistrationPayload(form, draft)
  assert.equal(payload.extra_fields.members.length, 1)
  assert.equal(payload.extra_fields.members[0].role, 'captain')
})

test('异常 schema 和人数不静默补造', () => {
  for (const form of [template({ min_team_member: 0 }), template({ max_team_member: 1 }), template({ form_member_schema: [] }), template({ form_team_schema: [{ field_key: 'x', label: '题目', type: 'select', required: true }] })]) {
    assert.throws(() => validateTemplate(form))
  }
})

test('识别已提供的数组及统一分页格式；拒绝其他格式', () => {
  const array = Array.from({ length: 21 }, (_, index) => ({ registration_id: index + 1 }))
  assert.equal(readList(array, 2, 20).items[0].registration_id, 21)
  assert.deepEqual(readList({ items: [{ registration_id: 21 }], total: 21 }, 2, 20).items, [{ registration_id: 21 }])
  assert.throws(() => readList({ rows: [], count: 0 }))
})
