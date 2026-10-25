<template>
  <section :aria-busy="loading" aria-label="推荐活动卡片">
    <el-skeleton v-if="loading" :rows="5" animated />
    <el-alert v-else-if="error" :title="error" type="error" show-icon :closable="false">
      <el-button size="small" @click="load(items)">重试活动卡片</el-button>
      <el-button size="small" @click="$router.push('/browse')">去活动广场</el-button>
    </el-alert>
    <template v-else>
      <p v-if="unavailable" class="unavailable" role="status">{{ unavailable }} 个推荐活动已不可报名或暂不可用，请调整标签或去活动广场查看。</p>
      <div class="card-grid">
        <ActivityCard v-for="d in displayItems" :key="d.activity_id" :activity="d.activity" :reasons="d.reasons" />
      </div>
      <el-button v-if="items.length && !displayItems.length" @click="$router.push('/browse')">去活动广场</el-button>
    </template>
  </section>
</template>

<script setup>
import { onBeforeUnmount, watch } from 'vue'
import { createApiClient } from '../api/request.js'
import { session, clearSession } from '../auth/session.js'
import { useRecommendedActivities } from '../domain/recommendedActivities.js'
import ActivityCard from './ActivityCard.vue'

// 接收活动 ID 列表 + 推荐理由；POD-1 内部查全量活动信息渲染卡片
const props = defineProps({
  items: { type: Array, default: () => [] },  // [{ activity_id, reasons }]
})

const request = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  getToken: () => session.value?.token,
  onUnauthorized: clearSession,
})

const { displayItems, unavailable, loading, error, load, clear } = useRecommendedActivities(request)
watch(() => [props.items, session.value?.token, session.value?.id, session.value?.role], () => {
  if (session.value?.role === 'student') load(props.items)
  else clear()
}, { immediate: true, deep: true })
onBeforeUnmount(clear)
</script>

<style scoped>
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:16px}
.unavailable{color:#606266;font-size:14px}
</style>
