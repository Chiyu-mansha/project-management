<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { activityStatusLabel, readList } from '../model.js'

const props = defineProps({ api: { type: Object, required: true }, userId: { type: [String, Number], required: true } })
const emit = defineEmits(['back', 'view'])
const items = ref([])
const page = ref(1)
const pageSize = 20
const total = ref(0)
const loading = ref(false)
const error = ref('')
let revision = 0
let controller

async function load(nextPage = page.value) {
  controller?.abort()
  controller = new AbortController()
  const ticket = ++revision
  page.value = nextPage
  error.value = ''
  loading.value = true
  items.value = []
  try {
    const list = readList(await props.api.getMyRegistrations(props.userId, page.value, pageSize, controller.signal), page.value, pageSize)
    if (ticket !== revision) return
    if (nextPage > 1 && !list.items.length && list.total <= (nextPage - 1) * pageSize) {
      return await load(Math.max(1, Math.ceil(list.total / pageSize)))
    }
    items.value = list.items
    total.value = list.total
  } catch (cause) {
    if (ticket === revision && cause.name !== 'AbortError') error.value = cause.message
  } finally {
    if (ticket === revision) loading.value = false
  }
}
watch(() => props.userId, () => load(1), { immediate: true })
onBeforeUnmount(() => { ++revision; controller?.abort() })
defineExpose({ refresh: () => load() })
</script>

<template>
  <section class="domain-page">
    <div class="page-heading">
      <el-button aria-label="返回" @click="emit('back')">← 返回</el-button>
      <h2>我报名的比赛</h2>
    </div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="feedback" />
    <el-skeleton v-if="loading" :rows="5" animated />
    <el-button v-else-if="error" @click="load()">重试</el-button>
    <el-empty v-else-if="!items.length" description="暂无报名记录" />
    <div v-else class="registration-list">
      <article v-for="item in items" :key="item.registration_id" class="registration-row">
        <div>
          <h3>{{ item.activity_name }}</h3>
          <div class="row-meta">
            <span>{{ activityStatusLabel(item.activity_status) }}</span>
            <span>{{ item.my_role === 'captain' ? '队长' : '队员' }}</span>
            <span>报名时间：{{ item.registered_at }}</span>
          </div>
        </div>
        <el-button type="primary" plain @click="emit('view', item)">查看</el-button>
      </article>
    </div>
    <el-pagination v-if="!loading && !error && total > pageSize" :current-page="page" :page-size="pageSize" :total="total" layout="prev, pager, next" @current-change="load" />
  </section>
</template>
