<script setup>
import { nextTick, ref } from 'vue'
import RegistrationDomain from '../../src/domain/RegistrationDomain.vue'

const domain = ref(null)
const role = ref('organizer')
const session = ref({ token: 'fixture-token', role: 'organizer', id: 10 })
const missingContract = ref(false)
const rejectSubmit = ref(false)
const rejectCancel = ref(false)
const hasRegistrations = ref(false)
const logs = ref([])
const cancelled = ref(false)
const form = ref({
  form_id: 1, organizer_id: 10,
  form_team_schema: [
    { field_key: 'project_name', label: '项目名称', type: 'text', required: true },
    { field_key: 'project_intro', label: '项目简介', type: 'textarea', required: false }
  ],
  form_member_schema: [
    { field_key: 'student_id', label: '学号', type: 'text', required: true },
    { field_key: 'name', label: '姓名', type: 'text', required: true },
    { field_key: 'major', label: '专业', type: 'text', required: false }
  ],
  min_team_member: 2, max_team_member: 4, created_at: '2026-10-01T14:00:00'
})
const extra = {
  team_extra: { project_name: 'AI盲人眼镜', project_intro: '项目介绍文字...' },
  members: [
    { role: 'captain', member_extra: { student_id: '2023001', name: '张三', major: '软件工程' } },
    { role: 'member', member_extra: { student_id: '2023002', name: '李四', major: '数字媒体' } }
  ]
}
const activityRecords = [{ registration_id: 1, user_id: 100, registered_at: '2026-10-09T10:30:00', extra_fields: extra }]
const mine = [
  { registration_id: 1, activity_name: '软件创新大赛', activity_status: 'published', registered_at: '2026-10-01T14:00:00', my_role: 'captain' },
  { registration_id: 5, activity_name: '智能硬件挑战赛', activity_status: 'published', registered_at: '2026-10-01T14:00:00', my_role: 'member' }
]

function reply(data, status = 200, message) {
  return new Response(JSON.stringify(message ? { code: status, message } : { code: 0, data }), { status })
}
window.fetch = async (url, options = {}) => {
  const parsed = new URL(url, window.location.origin)
  const method = options.method || 'GET'
  logs.value.push({ path: parsed.pathname + parsed.search, method, body: options.body ? JSON.parse(options.body) : undefined })
  if (options.headers.Authorization !== 'Bearer fixture-token') return reply(null, 401, '请先登录')
  if (/\/activities\/\d+\/forms$/.test(parsed.pathname)) {
    if (method === 'GET') return reply({ ...form.value, ...(parsed.pathname.includes('/2/') ? { min_team_member: 1, max_team_member: 1, form_team_schema: [] } : {}) })
    if (method === 'PUT' && hasRegistrations.value) return reply(null, 409, '活动已有报名记录，不能修改表单')
    Object.assign(form.value, JSON.parse(options.body))
    return reply({ form_id: 1 })
  }
  if (/\/activities\/\d+$/.test(parsed.pathname)) {
    return reply({ min_team_member: 2, max_team_member: 4, status: parsed.pathname.endsWith('/3') ? 'cancelled' : 'published' })
  }
  if (/\/activities\/\d+\/registrations$/.test(parsed.pathname)) {
    if (method === 'GET') return reply(hasRegistrations.value ? activityRecords : [])
    if (rejectSubmit.value) return reply(null, 409, '该成员已报名本活动')
    return reply({ registration_id: 1 })
  }
  if (/\/users\/\d+\/registrations$/.test(parsed.pathname)) return reply({ items: cancelled.value ? mine.slice(1) : mine, total: cancelled.value ? 1 : 2 })
  if (/\/registrations\/\d+$/.test(parsed.pathname)) {
    if (method === 'DELETE') {
      if (rejectCancel.value) return reply(null, 409, '已签到或已发凭证，请线下处理')
      cancelled.value = true
      return reply(null)
    }
    // The detail response shape is deliberately NOT specified by the test.
    // An explicit test-only adapter below uses known sample data in memory.
    return reply(null)
  }
  return reply(null, 404, '资源不存在')
}

// Only sample labels/keys already given by the user; not a proposed generation rule.
const fixtureGenerator = (label) => {
  const key = { '项目名称': 'project_name', '项目简介': 'project_intro', '专业': 'major' }[label]
  if (!key) throw new Error('测试仅使用文档题干示例')
  return key
}
const fixtureDetailReader = () => ({ teamSchema: form.value.form_team_schema, memberSchema: form.value.form_member_schema, teamExtra: extra.team_extra, members: extra.members, isIndividual: false })
async function switchRole(value) {
  role.value = value
  session.value = { token: 'fixture-token', role: value, id: value === 'organizer' ? 10 : 100 }
  await nextTick()
}
</script>

<template>
  <aside class="test-controls">
    <strong>文档样例验证（仅测试，不进入生产页面）</strong>
    <div>
      <el-button @click="switchRole('organizer')">发布者测试</el-button>
      <el-button @click="switchRole('student')">学生测试</el-button>
      <el-checkbox v-model="missingContract">缺失契约</el-checkbox>
      <el-checkbox v-model="rejectSubmit">报名失败</el-checkbox>
      <el-checkbox v-model="rejectCancel">取消拒绝</el-checkbox>
      <el-checkbox v-model="hasRegistrations">已有报名</el-checkbox>
    </div>
  </aside>
  <RegistrationDomain ref="domain" :session="session" :generate-field-key="missingContract ? undefined : fixtureGenerator" :read-registration-detail="missingContract ? undefined : fixtureDetailReader">
    <template #home="actions">
      <div class="domain-home">
        <template v-if="role === 'organizer'">
          <el-button @click="actions.openCreateForm(1)">创建表单</el-button>
          <el-button @click="actions.openFormTemplate(1)">查看模板</el-button>
          <el-button @click="actions.openActivityRegistrations(1)">获取报名信息</el-button>
        </template>
        <template v-else>
          <el-button @click="actions.openRegistration(1)">报名</el-button>
          <el-button @click="actions.openRegistration(2)">个人报名</el-button>
          <el-button @click="actions.openRegistration(3)">已取消活动报名</el-button>
          <el-button @click="actions.openMyRegistrations()">我的报名</el-button>
        </template>
      </div>
    </template>
  </RegistrationDomain>
  <details class="test-controls"><summary>测试请求记录</summary><pre id="request-log">{{ JSON.stringify(logs, null, 2) }}</pre></details>
</template>

<style>
body { margin: 0; font-family: system-ui, "Microsoft YaHei", sans-serif; }
.test-controls { padding: 16px; background: #f5f7fa; }
.test-controls > div { display: flex; flex-wrap: wrap; align-items: center; gap: 8px; margin-top: 12px; }
.test-controls pre { white-space: pre-wrap; }
</style>
