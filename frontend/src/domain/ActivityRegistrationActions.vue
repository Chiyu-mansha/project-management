<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import RegistrationDomain from './RegistrationDomain.vue'
import { ownsActivity, registrationBlockReason } from './activityAccess.js'

const props = defineProps({
  activity: { type: Object, required: true },
  session: { type: Object, default: null },
  baseUrl: { type: String, default: import.meta.env.VITE_API_BASE_URL || '/api' }
})
const emit = defineEmits(['back', 'form-saved', 'registration-submitted', 'registration-cancelled', 'session-expired'])
const domain = ref(null)
const now = ref(Date.now())
const timer = setInterval(() => { now.value = Date.now() }, 1000)
onBeforeUnmount(() => clearInterval(timer))
const blockReason = computed(() => registrationBlockReason(props.activity, now.value))
const owner = computed(() => ownsActivity(props.activity, props.session))
const student = computed(() => props.session?.role?.toLowerCase() === 'student' && !!props.session.token)

// A reused activity detail route must close the previous activity's forms/lists.
watch(() => props.activity.id, () => domain.value?.reset())
function relay(event, result) {
  emit(event, { activity_id: props.activity.id, ...result })
}
</script>

<template>
  <RegistrationDomain ref="domain" :session="session" :base-url="baseUrl"
    @back="emit('back')" @session-expired="emit('session-expired')"
    @form-saved="relay('form-saved', $event)"
    @registration-submitted="relay('registration-submitted', $event)"
    @registration-cancelled="relay('registration-cancelled', { registration_id: $event })">
    <template #home="actions">
      <section class="registration-actions" aria-label="活动报名操作">
        <template v-if="owner">
          <el-button :disabled="actions.opening" @click="actions.openCreateForm(activity.id)">创建报名表单</el-button>
          <el-button :disabled="actions.opening" @click="actions.openFormTemplate(activity.id)">查看报名表单</el-button>
          <el-button :disabled="actions.opening" @click="actions.openActivityRegistrations(activity.id)">查看报名名单</el-button>
        </template>
        <template v-else-if="student">
          <el-button type="primary" :disabled="!!blockReason || actions.opening" @click="actions.openRegistration(activity.id)">报名</el-button>
          <el-button :disabled="actions.opening" @click="actions.openMyRegistrations()">我的报名</el-button>
          <span v-if="blockReason" role="status" class="muted">{{ blockReason }}</span>
        </template>
        <p v-else-if="!session" class="muted">登录后可报名或管理报名表单。</p>
        <p v-else class="muted">仅本活动发布者可管理报名表单和名单。</p>
      </section>
    </template>
  </RegistrationDomain>
</template>

<style scoped>
.registration-actions { display: flex; flex-wrap: wrap; align-items: center; gap: 12px; margin: 20px 0; }
.registration-actions :deep(.el-button + .el-button) { margin-left: 0; }
</style>
