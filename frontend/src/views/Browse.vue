<template>
  <div>
    <h2 class="page-title">🎉 活动广场</h2>
    <div v-if="loading" v-loading="loading" style="min-height:200px"></div>
    <el-empty v-else-if="rows.length === 0" description="暂无活动" />
    <div v-else class="card-grid">
      <ActivityCard v-for="a in rows" :key="a.id" :activity="a" />
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { createApiClient } from '../api/request.js'
import { session } from '../auth/session.js'
import ActivityCard from './ActivityCard.vue'

const request = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  getToken: () => session.value?.token,
})

const rows = ref([])
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await request('/activities', { query: { status: 'published,ongoing', page_size: 100 } })
    rows.value = data.items || []
  } catch {
    rows.value = []
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.page-title{margin:0 0 16px;font-size:22px}
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
</style>
