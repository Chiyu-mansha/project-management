<script setup>
import { computed, nextTick, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createApiClient } from '../api/request.js'
import { createRegistrationApi } from '../api/registrations.js'
import FormTemplateDialog from './components/FormTemplateDialog.vue'
import RegistrationDialog from './components/RegistrationDialog.vue'
import RegistrationDetailDialog from './components/RegistrationDetailDialog.vue'
import MyRegistrations from './components/MyRegistrations.vue'
import ActivityRegistrations from './components/ActivityRegistrations.vue'
import './domain.css'

const props = defineProps({
  // Exact login result defined in the final document: { token, role, id }.
  session: { type: Object, default: null },
  baseUrl: { type: String, default: import.meta.env.VITE_API_BASE_URL || '/api' },
  generateFieldKey: Function,
  readRegistrationDetail: Function
})
const emit = defineEmits(['back', 'form-saved', 'registration-submitted', 'registration-cancelled'])
const api = createRegistrationApi(createApiClient({ baseUrl: props.baseUrl, getToken: () => props.session?.token }))
const templateDialog = ref(null)
const registrationDialog = ref(null)
const detailDialog = ref(null)
const myRegistrations = ref(null)
const page = ref('home')
const activityId = ref(null)
const opening = ref(false)
const student = computed(() => props.session?.role === 'student' && !!props.session?.token && props.session?.id != null)

function allowed(role) {
  if (!props.session?.token || props.session.id == null) {
    ElMessage.error('请先登录')
    return false
  }
  if (props.session.role !== role) {
    ElMessage.error('无权限访问')
    return false
  }
  return true
}
function back() {
  page.value = 'home'
  emit('back')
}
async function openCreateForm(id) {
  if (!allowed('organizer') || opening.value) return
  opening.value = true
  try { await templateDialog.value.openCreate(id) } finally { opening.value = false }
}
async function openFormTemplate(id) {
  if (!allowed('organizer') || opening.value) return
  opening.value = true
  try { await templateDialog.value.openView(id) } finally { opening.value = false }
}
async function openRegistration(id) {
  if (!allowed('student') || opening.value) return
  opening.value = true
  try { await registrationDialog.value.open(id) } finally { opening.value = false }
}
function openActivityRegistrations(id) {
  if (!allowed('organizer')) return
  activityId.value = id
  page.value = 'activity-registrations'
}
async function openMyRegistrations() {
  if (!allowed('student')) return
  page.value = 'my-registrations'
  await nextTick()
}
async function openRegistrationDetail(record) {
  if (!allowed('student')) return
  // Only records returned for the current user supply my_role; the detail adapter
  // does not infer permission from members[0], names, or editable form answers.
  await detailDialog.value.open(record)
}
async function submitted(result) {
  emit('registration-submitted', result)
  if (page.value === 'my-registrations') await myRegistrations.value?.refresh()
}
async function cancelled(id) {
  emit('registration-cancelled', id)
  if (page.value === 'my-registrations') await myRegistrations.value?.refresh()
}
watch(() => [props.session?.token, props.session?.id, props.session?.role], () => {
  page.value = 'home'
  opening.value = false
  templateDialog.value?.reset()
  registrationDialog.value?.reset()
  detailDialog.value?.reset()
})

// POD-1 calls these functions with an actual activity id from its own page.
defineExpose({ openCreateForm, openFormTemplate, openRegistration, openActivityRegistrations, openMyRegistrations, openRegistrationDetail })
</script>

<template>
  <div class="registration-domain" :aria-busy="opening">
    <template v-if="page === 'home'">
      <slot name="home" :open-create-form="openCreateForm" :open-form-template="openFormTemplate" :open-registration="openRegistration" :open-activity-registrations="openActivityRegistrations" :open-my-registrations="openMyRegistrations" :opening="opening">
        <div class="domain-home">
          <h2>报名管理</h2>
          <el-button v-if="student" type="primary" @click="openMyRegistrations">我报名的比赛</el-button>
          <p v-else class="muted">请从活动页面进入报名功能。</p>
        </div>
      </slot>
    </template>
    <MyRegistrations v-else-if="page === 'my-registrations' && student" ref="myRegistrations" :api="api" :user-id="session.id" @back="back" @view="openRegistrationDetail" />
    <ActivityRegistrations v-else-if="page === 'activity-registrations'" :api="api" :activity-id="activityId" @back="back" />
    <FormTemplateDialog ref="templateDialog" :api="api" :generate-field-key="generateFieldKey" @saved="emit('form-saved', $event)" />
    <RegistrationDialog ref="registrationDialog" :api="api" @submitted="submitted" />
    <RegistrationDetailDialog ref="detailDialog" :api="api" :read-detail="readRegistrationDetail" @cancelled="cancelled" />
  </div>
</template>
