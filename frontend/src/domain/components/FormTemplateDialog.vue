<script setup>
import { nextTick, onBeforeUnmount, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import SchemaEditor from './SchemaEditor.vue'
import { buildFormPayload, checkTeamLimits, createTemplateDraft, readList, validateTemplate } from '../model.js'

const props = defineProps({ api: { type: Object, required: true }, generateFieldKey: Function })
const emit = defineEmits(['saved'])
const visible = ref(false)
const mode = ref('create')
const activityId = ref(null)
const metadata = ref(null)
const template = ref(null)
const draft = ref(createTemplateDraft())
const loading = ref(false)
const saving = ref(false)
const checking = ref(false)
const hasRegistrations = ref(false)
const error = ref('')
let revision = 0
let resetVersion = 0
let controller

watch(visible, (open) => {
  if (!open) {
    ++revision
    controller?.abort()
  }
})

async function load(id, nextMode) {
  controller?.abort()
  controller = new AbortController()
  const ticket = ++revision
  activityId.value = id
  mode.value = nextMode
  template.value = null
  metadata.value = null
  draft.value = createTemplateDraft()
  hasRegistrations.value = false
  error.value = ''
  visible.value = true
  loading.value = true
  try {
    if (nextMode === 'create') {
      const activity = await props.api.getActivity(id, controller.signal)
      checkTeamLimits(activity)
      if (ticket !== revision) return
      metadata.value = activity
    } else {
      const form = validateTemplate(await props.api.getForm(id, controller.signal))
      if (ticket !== revision) return
      template.value = form
      metadata.value = form
      draft.value = createTemplateDraft(form)
    }
  } catch (cause) {
    if (ticket === revision && cause.name !== 'AbortError') error.value = cause.message
  } finally {
    if (ticket === revision) loading.value = false
  }
}

async function edit() {
  if (checking.value || hasRegistrations.value || !template.value) return
  checking.value = true
  error.value = ''
  const ticket = revision
  try {
    const list = readList(await props.api.getActivityRegistrations(activityId.value, 1, 20, controller.signal))
    if (ticket !== revision) return
    if (list.total > 0) {
      hasRegistrations.value = true
      error.value = '活动已有报名记录，不能修改表单'
      return
    }
    draft.value = createTemplateDraft(template.value)
    mode.value = 'edit'
  } catch (cause) {
    if (ticket === revision && cause.name !== 'AbortError') error.value = cause.message
  } finally {
    checking.value = false
  }
}

async function save() {
  if (saving.value || loading.value || !metadata.value || mode.value === 'view') return
  saving.value = true
  error.value = ''
  const id = activityId.value
  const ticket = revision
  const wasEdit = mode.value === 'edit'
  const sessionVersion = resetVersion
  try {
    const payload = await buildFormPayload(draft.value, props.generateFieldKey)
    if (ticket !== revision) return
    const result = wasEdit ? await props.api.updateForm(id, payload, controller.signal) : await props.api.createForm(id, payload, controller.signal)
    if (ticket !== revision) return
    ElMessage.success(wasEdit ? '表单修改成功' : '表单创建成功')
    saving.value = false
    visible.value = false
    emit('saved', result)
    if (wasEdit) {
      await nextTick()
      if (sessionVersion === resetVersion) await load(id, 'view')
    }
  } catch (cause) {
    if (ticket === revision) error.value = cause.message
  } finally {
    if (ticket === revision) saving.value = false
  }
}

function close(done) {
  if (!saving.value && !checking.value) done()
}
function dismiss() {
  if (!saving.value && !checking.value) visible.value = false
}
function reset() {
  ++revision
  ++resetVersion
  controller?.abort()
  visible.value = false
  saving.value = false
  loading.value = false
  checking.value = false
  metadata.value = null
  template.value = null
}
onBeforeUnmount(reset)
defineExpose({
  openCreate: (id) => load(id, 'create'),
  openView: (id) => load(id, 'view'),
  close: dismiss,
  reset
})
</script>

<template>
  <el-dialog v-model="visible" width="min(820px, calc(100vw - 32px))" :show-close="false" :before-close="close" :close-on-click-modal="false" :close-on-press-escape="!saving && !checking" destroy-on-close :title="mode === 'create' ? '创建报名表单' : mode === 'edit' ? '编辑报名表单' : '查看报名表单'">
    <template #header="{ titleId }">
      <div class="dialog-heading">
        <h2 :id="titleId">{{ mode === 'create' ? '创建报名表单' : mode === 'edit' ? '编辑报名表单' : '查看报名表单' }}</h2>
        <div class="heading-actions">
          <el-button v-if="mode === 'view' && template" :disabled="loading || hasRegistrations" :loading="checking" @click="edit">编辑</el-button>
          <el-button v-if="mode === 'edit'" type="primary" :loading="saving" @click="save">保存</el-button>
          <el-button :disabled="saving || checking" aria-label="关闭表单" @click="dismiss">×</el-button>
        </div>
      </div>
    </template>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="feedback" />
    <el-skeleton v-if="loading" :rows="5" animated />
    <template v-else-if="metadata">
      <div class="metadata">
        <span>活动 ID：{{ activityId }}</span>
        <span>参赛人数：{{ metadata.min_team_member }}–{{ metadata.max_team_member }} 人（含队长）</span>
      </div>
      <SchemaEditor v-model="draft.form_team_schema" :readonly="mode === 'view'" :disabled="saving" />
      <SchemaEditor v-model="draft.form_member_schema" member :readonly="mode === 'view'" :disabled="saving" />
    </template>
    <el-button v-else @click="load(activityId, mode)">重试</el-button>
    <template v-if="mode === 'create' && metadata" #footer>
      <el-button type="primary" :loading="saving" :disabled="loading" @click="save">提交表单</el-button>
    </template>
  </el-dialog>
</template>
