<template>
  <div>
    <h2 class="page-title">🎉 活动广场</h2>
    <el-skeleton v-if="loading" :rows="6" animated />
    <el-alert v-else-if="error" :title="error" type="error" show-icon :closable="false">
      <el-button @click="load(page)">重试活动广场</el-button>
    </el-alert>
    <el-empty v-else-if="rows.length === 0" description="暂无活动" />
    <div v-else class="card-grid">
      <ActivityCard v-for="a in rows" :key="a.id" :activity="a" />
    </div>
    <el-pagination v-if="!loading && !error && total > pageSize" :current-page="page" :page-size="pageSize"
      :total="total" layout="prev, pager, next" @current-change="load" />
  </div>
</template>

<script setup>
import { onBeforeUnmount, ref, watch } from 'vue'
import { createApiClient } from '../api/request.js'
import { session, clearSession } from '../auth/session.js'
import { readList } from '../domain/model.js'
import ActivityCard from './ActivityCard.vue'

const request = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  getToken: () => session.value?.token,
  onUnauthorized: clearSession,
})

const rows = ref([])
const loading = ref(false)
const error = ref('')
const total = ref(0)
const page = ref(1)
const pageSize = 20
let revision = 0
let controller

async function load(nextPage = 1) {
  controller?.abort()
  controller = new AbortController()
  const ticket = ++revision
  rows.value = []
  total.value = 0
  error.value = ''
  page.value = nextPage
  loading.value = false
  if (!session.value) return
  loading.value = true
  try {
    const data = readList(await request('/activities', {
      query: { status: 'published,ongoing', page: nextPage, page_size: pageSize }, signal: controller.signal
    }))
    if (ticket !== revision) return
    rows.value = data.items
    total.value = data.total
  } catch (cause) {
    if (ticket === revision && cause.name !== 'AbortError') error.value = cause.message
  } finally {
    if (ticket === revision) loading.value = false
  }
}

watch(() => [session.value?.token, session.value?.id, session.value?.role], () => load(1), { immediate: true })
onBeforeUnmount(() => { ++revision; controller?.abort() })
</script>

<style scoped>
.page-title{margin:0 0 16px;font-size:22px}
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
.el-pagination{margin-top:24px;justify-content:center}
</style>
