<template>
  <div class="card-grid">
    <ActivityCard v-for="d in displayItems" :key="d.activity_id" :activity="d.activity" :reasons="d.reasons" />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { createApiClient } from '../api/request.js'
import { session } from '../auth/session.js'
import ActivityCard from './ActivityCard.vue'

// 接收活动 ID 列表 + 推荐理由；POD-1 内部查全量活动信息渲染卡片
const props = defineProps({
  items: { type: Array, default: () => [] },  // [{ activity_id, reasons }]
})

const request = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  getToken: () => session.value?.token,
})

const displayItems = ref([])

watch(
  () => props.items,
  async (items) => {
    if (!items || items.length === 0) {
      displayItems.value = []
      return
    }
    const ids = items.map((i) => i.activity_id).join(',')
    try {
      const actData = await request('/activities', { query: { ids, page_size: 100 } })
      const actMap = Object.fromEntries((actData.items || []).map((a) => [a.id, a]))
      displayItems.value = items
        .map((i) => ({ activity_id: i.activity_id, reasons: i.reasons, activity: actMap[i.activity_id] }))
        .filter((x) => x.activity)
    } catch {
      displayItems.value = []
    }
  },
  { immediate: true }
)
</script>

<style scoped>
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
</style>
