<script setup>
import { computed, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import DynamicFields from './DynamicFields.vue'
import { buildRegistrationPayload, createRegistrationDraft, newMember, validateTemplate } from '../model.js'

const props = defineProps({ api: { type: Object, required: true } })
const emit = defineEmits(['submitted'])
const visible = ref(false)
const template = ref(null)
const activityId = ref(null)
const draft = ref(null)
const opening = ref(false)
const saving = ref(false)
const error = ref('')
const individual = computed(() => template.value?.min_team_member === 1 && template.value?.max_team_member === 1)
let revision = 0
let controller

watch(visible, (open) => {
  if (!open) {
    ++revision
    controller?.abort()
  }
})

async function open(id) {
  controller?.abort()
  controller = new AbortController()
  const ticket = ++revision
  opening.value = true
  error.value = ''
  try {
    // Fetch before presenting the fill-in popup, as required by section 7.5.
    const form = validateTemplate(await props.api.getForm(id, controller.signal))
    const activity = await props.api.getActivity(id, controller.signal)
    if (ticket !== revision) return
    if (activity.status === 'cancelled') {
      ElMessage.error('活动已取消，不能报名')
      return
    }
    activityId.value = id
    template.value = form
    draft.value = createRegistrationDraft(form)
    visible.value = true
  } catch (cause) {
    if (ticket === revision && cause.name !== 'AbortError') ElMessage.error(cause.message)
  } finally {
    if (ticket === revision) opening.value = false
  }
}

function addMember() {
  if (saving.value || draft.value.members.length >= template.value.max_team_member) return
  draft.value.members.push(newMember(template.value.form_member_schema))
}
function removeMember(index) {
  if (saving.value || index === 0 || draft.value.members.length <= template.value.min_team_member) return
  draft.value.members.splice(index, 1)
}
async function submit() {
  if (saving.value || !template.value) return
  error.value = ''
  const ticket = revision
  try {
    const payload = buildRegistrationPayload(template.value, draft.value)
    saving.value = true
    const result = await props.api.submitRegistration(activityId.value, payload)
    if (ticket !== revision) return
    ElMessage.success('报名提交成功')
    saving.value = false
    visible.value = false
    emit('submitted', result)
  } catch (cause) {
    if (ticket === revision) error.value = cause.message
  } finally {
    if (ticket === revision) saving.value = false
  }
}
function dismiss() {
  if (!saving.value) visible.value = false
}
function reset() {
  ++revision
  controller?.abort()
  visible.value = false
  saving.value = false
  opening.value = false
  template.value = null
  draft.value = null
}
defineExpose({ open, close: dismiss, reset, opening })
</script>

<template>
  <el-dialog v-model="visible" title="填写报名表单" width="min(760px, calc(100vw - 32px))" :show-close="!saving" :before-close="(done) => { if (!saving) done() }" :close-on-click-modal="false" :close-on-press-escape="!saving" destroy-on-close>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="feedback" />
    <template v-if="template && draft">
      <section class="form-section">
        <h3>队伍信息（全队填写一次）</h3>
        <DynamicFields v-model="draft.teamAnswers" :schema="template.form_team_schema" :disabled="saving" prefix="team" />
      </section>
      <section class="form-section">
        <div class="section-heading">
          <h3>{{ individual ? '报名人信息' : '队员信息（每位队员单独填写）' }}</h3>
          <span v-if="!individual" class="muted">{{ draft.members.length }} / {{ template.max_team_member }} 人</span>
        </div>
        <p v-if="!individual" class="muted">参赛人数：{{ template.min_team_member }}–{{ template.max_team_member }} 人（含队长）</p>
        <div v-for="(member, index) in draft.members" :key="member._uiId" class="member-card">
          <div v-if="!individual" class="section-heading">
            <el-tag :type="index === 0 ? 'primary' : 'info'">{{ index === 0 ? '队长' : '队员' }}</el-tag>
            <el-button v-if="index > 0" :disabled="saving || draft.members.length <= template.min_team_member" :aria-label="`删除第 ${index + 1} 位队员`" @click="removeMember(index)">删除队员</el-button>
          </div>
          <DynamicFields v-model="member.answers" :schema="template.form_member_schema" :disabled="saving" :prefix="member._uiId" />
        </div>
        <el-button v-if="!individual" :disabled="saving || draft.members.length >= template.max_team_member" @click="addMember">＋ 添加队员</el-button>
      </section>
    </template>
    <template #footer>
      <el-button type="primary" :loading="saving" @click="submit">提交报名</el-button>
    </template>
  </el-dialog>
</template>
