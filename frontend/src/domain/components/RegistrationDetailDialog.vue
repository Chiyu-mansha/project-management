<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import AnswersView from './AnswersView.vue'
import { validateDetailView } from '../model.js'
import { readRegistrationDetail } from '../adapters.js'

const props = defineProps({
  api: { type: Object, required: true },
  readDetail: { type: Function, default: readRegistrationDetail }
})
const emit = defineEmits(['cancelled'])
const visible = ref(false)
const record = ref(null)
const detail = ref(null)
const loading = ref(false)
const saving = ref(false)
const error = ref('')
let revision = 0
let controller
watch(visible, (open) => {
  if (!open) {
    ++revision
    controller?.abort()
  }
})

async function open(row) {
  controller?.abort()
  controller = new AbortController()
  const ticket = ++revision
  record.value = row
  detail.value = null
  loading.value = true
  error.value = ''
  visible.value = true
  try {
    const data = await props.api.getRegistration(row.registration_id, controller.signal)
    const view = validateDetailView(await props.readDetail(data, { record: row, signal: controller.signal }))
    if (ticket === revision) detail.value = view
  } catch (cause) {
    if (ticket === revision && cause.name !== 'AbortError') error.value = cause.message
  } finally {
    if (ticket === revision) loading.value = false
  }
}

async function cancel() {
  if (saving.value || loading.value || !detail.value || record.value?.my_role !== 'captain') return
  saving.value = true
  error.value = ''
  const ticket = revision
  try {
    // Backend checks credentials. The frontend neither reads nor writes POD-3 tables.
    await props.api.cancelRegistration(record.value.registration_id, controller.signal)
    if (ticket !== revision) return
    ElMessage.success('已取消报名')
    saving.value = false
    visible.value = false
    emit('cancelled', record.value.registration_id)
  } catch (cause) {
    // Preserve the backend's human-readable reason, including offline-handling refusal.
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
  loading.value = false
  record.value = null
  detail.value = null
}
onBeforeUnmount(reset)
defineExpose({ open, close: dismiss, reset })
</script>

<template>
  <el-dialog v-model="visible" title="报名详情" width="min(760px, calc(100vw - 32px))" :show-close="!saving" :before-close="(done) => { if (!saving) done() }" :close-on-click-modal="false" :close-on-press-escape="!saving" destroy-on-close>
    <h3 v-if="record?.activity_name">{{ record.activity_name }}</h3>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="feedback" />
    <el-skeleton v-if="loading" :rows="5" animated />
    <template v-else-if="detail">
      <section class="form-section">
        <h3>队伍信息</h3>
        <AnswersView :schema="detail.teamSchema" :answers="detail.teamExtra" />
      </section>
      <section class="form-section">
        <h3>{{ detail.isIndividual ? '报名人信息' : '队员信息' }}</h3>
        <div v-for="(member, index) in detail.members" :key="index" class="member-card">
          <el-tag v-if="!detail.isIndividual" :type="member.role === 'captain' ? 'primary' : 'info'">{{ member.role === 'captain' ? '队长' : '队员' }}</el-tag>
          <AnswersView :schema="detail.memberSchema" :answers="member.member_extra" />
        </div>
      </section>
    </template>
    <el-button v-else @click="open(record)">重试</el-button>
    <template v-if="detail && record?.my_role === 'captain'" #footer>
      <p class="muted">已签到或已发凭证的报名不能取消，请线下处理。</p>
      <el-button type="danger" :loading="saving" @click="cancel">取消报名</el-button>
    </template>
  </el-dialog>
</template>
