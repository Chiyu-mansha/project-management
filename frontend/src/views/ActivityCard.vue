<template>
  <div class="act-card" role="link" tabindex="0" :aria-label="`查看活动：${activity.title}`"
    @click="$router.push(`/activities/${activity.id}`)" @keydown.enter="$router.push(`/activities/${activity.id}`)">
    <div class="cover" :style="coverStyle">
      <img v-if="activity.cover_image" :src="activity.cover_image" alt="" />
      <span v-else class="cover-emoji">{{ typeEmoji(activity.type) }}</span>
    </div>
    <div class="card-body">
      <div class="title">{{ activity.title }}</div>
      <div class="meta">⏰ {{ fmtTime(activity.start_time) }}</div>
      <div class="meta">📍 {{ activity.location || '待定' }}</div>
      <div class="tags">
        <el-tag v-if="activity.type" size="small" type="primary" effect="plain">{{ activity.type }}</el-tag>
        <el-tag v-if="activity.comprehensive_score" size="small" type="success" effect="plain">综测加分</el-tag>
        <el-tag v-if="activity.has_ticket" size="small" type="warning" effect="plain">电子票</el-tag>
        <el-tag v-for="r in reasons" :key="r" size="small" type="danger" effect="plain">🔥 {{ r }}</el-tag>
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  activity: { type: Object, required: true },
  reasons: { type: Array, default: () => [] },
})

const EMOJI = { '学科类': '📚', '文体类': '🎭', '科创竞赛': '🏆', '社会实践': '🤝' }
const GRADIENT = {
  '学科类': 'linear-gradient(135deg,#6366f1,#8b5cf6)',
  '文体类': 'linear-gradient(135deg,#f59e0b,#f97316)',
  '科创竞赛': 'linear-gradient(135deg,#0ea5e9,#22d3ee)',
  '社会实践': 'linear-gradient(135deg,#22c55e,#4ade80)',
}
const typeEmoji = (t) => EMOJI[t] || '🎉'
const coverStyle = computed(() => ({ background: GRADIENT[props.activity.type] || 'linear-gradient(135deg,#94a3b8,#cbd5e1)' }))
const fmtTime = (s) => (s ? String(s).replace('T', ' ').slice(0, 16) : '时间待定')
</script>

<style scoped>
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
