<template>
  <div>
    <h2 class="page-title">🎉 活动广场</h2>
    <div v-if="loading" v-loading="loading" style="min-height:200px"></div>
    <el-empty v-else-if="rows.length === 0" description="暂无活动" />
    <div v-else class="card-grid">
      <div v-for="a in rows" :key="a.id" class="act-card" @click="$router.push(`/activities/${a.id}`)">
        <div class="cover" :style="coverStyle(a)">
          <img v-if="a.cover_image" :src="a.cover_image" alt="" />
          <span v-else class="cover-emoji">{{ typeEmoji(a.type) }}</span>
        </div>
        <div class="card-body">
          <div class="title">{{ a.title }}</div>
          <div class="meta">⏰ {{ fmtTime(a.start_time) }}</div>
          <div class="meta">📍 {{ a.location || '待定' }}</div>
          <div class="tags">
            <el-tag v-if="a.type" size="small" type="primary" effect="plain">{{ a.type }}</el-tag>
            <el-tag v-if="a.comprehensive_score" size="small" type="success" effect="plain">综测加分</el-tag>
            <el-tag v-if="a.has_ticket" size="small" type="warning" effect="plain">电子票</el-tag>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { createApiClient } from '../api/request.js'
import { session } from '../auth/session.js'

const request = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  getToken: () => session.value?.token,
})

const rows = ref([])
const loading = ref(false)

const EMOJI = { '学科类': '📚', '文体类': '🎭', '科创竞赛': '🏆', '社会实践': '🤝' }
const GRADIENT = {
  '学科类': 'linear-gradient(135deg,#6366f1,#8b5cf6)',
  '文体类': 'linear-gradient(135deg,#f59e0b,#f97316)',
  '科创竞赛': 'linear-gradient(135deg,#0ea5e9,#22d3ee)',
  '社会实践': 'linear-gradient(135deg,#22c55e,#4ade80)',
}
const typeEmoji = (t) => EMOJI[t] || '🎉'
const coverStyle = (a) => ({ background: GRADIENT[a.type] || 'linear-gradient(135deg,#94a3b8,#cbd5e1)' })
const fmtTime = (s) => (s ? String(s).replace('T', ' ').slice(0, 16) : '时间待定')

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
.card-grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:16px}
.act-card{background:#fff;border-radius:12px;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.06);cursor:pointer;transition:transform .2s,box-shadow .2s}
.act-card:hover{transform:translateY(-4px);box-shadow:0 6px 20px rgba(0,0,0,.12)}
.cover{height:130px;display:flex;align-items:center;justify-content:center}
.cover img{width:100%;height:100%;object-fit:cover}
.cover-emoji{font-size:52px}
.card-body{padding:12px 14px}
.title{font-size:16px;font-weight:600;margin-bottom:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.meta{font-size:13px;color:#666;margin-bottom:3px}
.tags{display:flex;gap:6px;flex-wrap:wrap;margin-top:6px}
</style>
