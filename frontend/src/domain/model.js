import { generateFieldKey as defaultGenerateFieldKey } from './fieldKeys.js'

let nextUiId = 0
export const newUiId = () => `row-${++nextUiId}`
export const FIXED_MEMBER_FIELDS = Object.freeze([
  Object.freeze({ field_key: 'student_id', label: '学号', type: 'text', required: true }),
  Object.freeze({ field_key: 'name', label: '姓名', type: 'text', required: true })
])

export function isFixedMemberField(field) {
  return FIXED_MEMBER_FIELDS.some((fixed) => fixed.field_key === field.field_key)
}

function checkSchema(schema, isMember = false) {
  if (!Array.isArray(schema)) throw new Error('报名表加载失败，请稍后重试')
  const seen = new Set()
  for (const field of schema) {
    if (!field || typeof field.field_key !== 'string' || !field.field_key.trim() ||
        typeof field.label !== 'string' || !field.label.trim() ||
        !['text', 'textarea'].includes(field.type) || typeof field.required !== 'boolean' ||
        seen.has(field.field_key)) throw new Error('报名表加载失败，请稍后重试')
    seen.add(field.field_key)
  }
  if (isMember) {
    for (const fixed of FIXED_MEMBER_FIELDS) {
      const field = schema.find((item) => item.field_key === fixed.field_key)
      if (!field || field.label !== fixed.label || field.type !== 'text' || field.required !== true) {
        throw new Error('报名表加载失败，请稍后重试')
      }
    }
  }
}

export function validateTemplate(template) {
  checkSchema(template?.form_team_schema)
  checkSchema(template?.form_member_schema, true)
  checkTeamLimits(template)
  return template
}

export function checkTeamLimits(activity) {
  const min = activity?.min_team_member
  const max = activity?.max_team_member
  if (!Number.isInteger(min) || !Number.isInteger(max) || min < 1 || max < min) {
    throw new Error('报名人数信息加载失败，请稍后重试')
  }
}

export function createTemplateDraft(template) {
  const row = (field) => ({ ...field, _uiId: newUiId() })
  return {
    form_team_schema: (template?.form_team_schema || []).map(row),
    form_member_schema: (template?.form_member_schema || FIXED_MEMBER_FIELDS).map(row)
  }
}

export function newQuestion() {
  return { field_key: '', label: '', type: 'text', required: false, _uiId: newUiId() }
}

export async function buildFormPayload(draft, generateFieldKey = defaultGenerateFieldKey) {
  const output = {}
  for (const section of ['form_team_schema', 'form_member_schema']) {
    const rows = draft[section]
    if (!Array.isArray(rows)) throw new Error('表单内容无效')
    const seen = new Set()
    // Reserve every existing key before generating, including fields later in the list.
    const reserved = new Set(rows.map((field) => field.field_key).filter(Boolean))
    output[section] = []
    for (const [index, field] of rows.entries()) {
      const title = section === 'form_team_schema' ? '队伍题目' : '队员题目'
      if (typeof field.label !== 'string' || !field.label.trim()) throw new Error(`${title}第 ${index + 1} 项题干不能为空`)
      if (!['text', 'textarea'].includes(field.type) || typeof field.required !== 'boolean') throw new Error(`${title}第 ${index + 1} 项配置无效`)
      let key = field.field_key
      if (!key) {
        if (typeof generateFieldKey !== 'function') {
          throw new Error('题目标识生成失败，请稍后重试')
        }
        key = await generateFieldKey(field.label)
        if (typeof key !== 'string' || !key.trim()) throw new Error(`${title}第 ${index + 1} 项暂时无法保存`)
        const baseKey = key
        let suffix = 2
        while (reserved.has(key)) key = `${baseKey}_${suffix++}`
        reserved.add(key)
        // Keep identifiers stable on subsequent saves; UI-only values never enter JSON.
        field.field_key = key
      }
      if (seen.has(key)) throw new Error(`${title}中存在重复题目标识，请调整题干`)
      seen.add(key)
      output[section].push({ field_key: key, label: field.label, type: field.type, required: field.required })
    }
    checkSchema(output[section], section === 'form_member_schema')
  }
  return output
}

export const emptyAnswers = (schema) => Object.fromEntries(schema.map((field) => [field.field_key, '']))
export const newMember = (schema, role = 'member') => ({ _uiId: newUiId(), role, answers: emptyAnswers(schema) })

export function createRegistrationDraft(template) {
  validateTemplate(template)
  return {
    teamAnswers: emptyAnswers(template.form_team_schema),
    members: Array.from({ length: template.min_team_member }, (_, index) => newMember(template.form_member_schema, index === 0 ? 'captain' : 'member'))
  }
}

function validateAnswers(schema, answers, title) {
  for (const field of schema) {
    const value = answers?.[field.field_key]
    if (typeof value !== 'string') throw new Error(`${title}的“${field.label}”填写内容无效`)
    if (field.required && !value.trim()) throw new Error(`请填写${title}的“${field.label}”`)
  }
}

const selectAnswers = (schema, answers) => Object.fromEntries(schema.map((field) => [field.field_key, answers[field.field_key]]))

export function buildRegistrationPayload(template, draft) {
  validateTemplate(template)
  validateAnswers(template.form_team_schema, draft.teamAnswers, '队伍信息')
  if (!Array.isArray(draft.members) || draft.members.length < template.min_team_member || draft.members.length > template.max_team_member) {
    throw new Error(`报名人数须为 ${template.min_team_member}–${template.max_team_member} 人（含队长）`)
  }
  const studentIds = new Set()
  draft.members.forEach((member, index) => {
    if (member.role !== (index === 0 ? 'captain' : 'member')) throw new Error('队长须为第一位报名人')
    validateAnswers(template.form_member_schema, member.answers, `第 ${index + 1} 位报名人`)
    const studentId = member.answers.student_id.trim()
    if (studentIds.has(studentId)) throw new Error('同一报名中不能出现重复学号')
    studentIds.add(studentId)
  })
  return {
    extra_fields: {
      team_extra: selectAnswers(template.form_team_schema, draft.teamAnswers),
      members: draft.members.map((member) => ({
        role: member.role,
        member_extra: selectAnswers(template.form_member_schema, member.answers)
      }))
    }
  }
}

// Both list representations appear in the supplied documents. No new DTO is added.
export function readList(data, page = 1, pageSize = 20) {
  if (Array.isArray(data)) return { items: data.slice((page - 1) * pageSize, page * pageSize), total: data.length, allItems: data }
  if (data && Array.isArray(data.items) && Number.isInteger(data.total) && data.total >= 0) {
    return { items: data.items, total: data.total, allItems: null }
  }
  throw new Error('列表加载失败，请稍后重试')
}

// Internal display data; adapters.js maps the implemented backend response.
export function validateDetailView(view) {
  checkSchema(view?.teamSchema)
  checkSchema(view?.memberSchema, true)
  if (!view.teamExtra || typeof view.teamExtra !== 'object' || !Array.isArray(view.members) ||
      typeof view.isIndividual !== 'boolean' || view.members.length < 1) throw new Error('报名详情加载失败，请稍后重试')
  for (const member of view.members) {
    if (!member || !['captain', 'member'].includes(member.role) || !member.member_extra || typeof member.member_extra !== 'object') {
      throw new Error('报名详情加载失败，请稍后重试')
    }
  }
  return view
}

export const activityStatusLabel = (status) => ({
  draft: '草稿', published: '已发布', ongoing: '进行中', finished: '已结束', cancelled: '已取消'
})[status] || status
