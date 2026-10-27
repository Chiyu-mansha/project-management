<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { readList, validateTemplate } from '../model.js'

const props = defineProps({ api: { type: Object, required: true }, activityId: { type: [String, Number], required: true } })
const emit = defineEmits(['back'])
const template = ref(null)
const items = ref([])
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)
const error = ref('')
const individual = computed(() => template.value?.min_team_member === 1 && template.value?.max_team_member === 1)
let revision = 0
let controller

async function load(nextPage = page.value) {
  controller?.abort()
  controller = new AbortController()
  const ticket = ++revision
  page.value = nextPage
  items.value = []
  error.value = ''
  loading.value = true
  try {
    const [form, data] = await Promise.all([
      props.api.getForm(props.activityId, controller.signal),
      props.api.getActivityRegistrations(props.activityId, nextPage, pageSize, controller.signal)
    ])
    const checked = validateTemplate(form)
    const list = readList(data, nextPage, pageSize)
    if (ticket !== revision) return
    template.value = checked
    items.value = list.items
    total.value = list.total
  } catch (cause) {
    if (ticket === revision && cause.name !== 'AbortError') error.value = cause.message
  } finally {
    if (ticket === revision) loading.value = false
  }
}
watch(() => props.activityId, () => load(1), { immediate: true })
onBeforeUnmount(() => { ++revision; controller?.abort() })
defineExpose({ refresh: () => load() })
</script>

<template>
  <section class="domain-page">
    <div class="page-heading">
      <el-button aria-label="返回已发布比赛" @click="emit('back')">← 返回</el-button>
      <h2>报名信息</h2>
    </div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="feedback" />
    <el-skeleton v-if="loading" :rows="5" animated />
    <el-button v-else-if="error" @click="load()">重试</el-button>
    <template v-else-if="template">
      <p class="muted">共 {{ total }} {{ individual ? '人' : '支队伍' }}报名</p>
      <el-table :data="items" row-key="registration_id" empty-text="暂无报名记录" border>
        <el-table-column type="expand">
          <template #default="{ row }">
            <div class="expanded-members">
              <h3>{{ individual ? '报名人信息' : '队员信息' }}</h3>
              <el-table :data="row.extra_fields.members" border>
                <el-table-column v-if="!individual" label="角色" width="100">
                  <template #default="{ row: member }">{{ member.role === 'captain' ? '队长' : '队员' }}</template>
                </el-table-column>
                <el-table-column v-for="field in template.form_member_schema" :key="field.field_key" :label="field.label" min-width="140">
                  <template #default="{ row: member }"><span class="preserve-text">{{ member.member_extra[field.field_key] || '—' }}</span></template>
                </el-table-column>
              </el-table>
            </div>
          </template>
        </el-table-column>
        <el-table-column prop="registration_id" label="报名编号" width="110" />
        <el-table-column v-for="field in template.form_team_schema" :key="field.field_key" :label="field.label" min-width="160">
          <template #default="{ row }"><span class="preserve-text">{{ row.extra_fields.team_extra[field.field_key] || '—' }}</span></template>
        </el-table-column>
        <el-table-column prop="registered_at" label="报名时间" min-width="200" />
      </el-table>
      <el-pagination v-if="total > pageSize" :current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="load" />
    </template>
  </section>
</template>
