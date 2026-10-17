<template>
  <div>
    <div class="detail-head">
      <h2>{{ act.title || (loading ? '加载中…' : '活动详情') }}</h2>
      <div>
        <el-button v-if="owner" type="warning" @click="$router.push(`/activities/${act.id}/edit`)">编辑</el-button>
        <el-button @click="$router.push('/activities')">返回列表</el-button>
      </div>
    </div>

    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
    <el-button v-if="error" @click="load">重试</el-button>
    <el-skeleton v-if="loading && !act.id" :rows="6" animated />
    <el-descriptions v-if="act.id" :column="2" border v-loading="loading">
      <el-descriptions-item label="类型">{{ act.type || '-' }}</el-descriptions-item>
      <el-descriptions-item label="状态">
        <el-tag :type="statusType(act.status)">{{ statusText(act.status) }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="地点">{{ act.location || '-' }}</el-descriptions-item>
      <el-descriptions-item label="开始时间">{{ fmtTime(act.start_time) }}</el-descriptions-item>
      <el-descriptions-item label="结束时间">{{ fmtTime(act.end_time) }}</el-descriptions-item>
      <el-descriptions-item label="报名截止">{{ fmtTime(act.signup_deadline) }}</el-descriptions-item>
      <el-descriptions-item label="队伍人数">{{ act.min_team_member }} ~ {{ act.max_team_member }} 人</el-descriptions-item>
      <el-descriptions-item label="队伍上限">{{ act.max_participants ?? '不限' }}</el-descriptions-item>
      <el-descriptions-item label="电子票">{{ act.has_ticket ? '是' : '否' }}</el-descriptions-item>
      <el-descriptions-item label="综合素养分">{{ act.comprehensive_score ? '能加' : '不加' }}</el-descriptions-item>
      <el-descriptions-item label="操行分">{{ act.conduct_score ?? '-' }}</el-descriptions-item>
      <el-descriptions-item label="创新分">{{ act.innovation_score ?? '-' }}</el-descriptions-item>
      <el-descriptions-item label="标签">{{ act.tags || '-' }}</el-descriptions-item>
      <el-descriptions-item label="报名条件" :span="2">{{ act.requirements || '-' }}</el-descriptions-item>
      <el-descriptions-item label="简介" :span="2">{{ act.description || '-' }}</el-descriptions-item>
    </el-descriptions>
    <ActivityRegistrationActions v-if="act.id" :activity="act" :session="session"
      @session-expired="clearSession" @form-saved="load" @registration-submitted="load" @registration-cancelled="load" />
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ActivityRegistrationActions from '../domain/ActivityRegistrationActions.vue'
import { ownsActivity } from '../domain/activityAccess.js'
import { createApiClient } from '../api/request.js'
import { session, clearSession } from '../auth/session.js'

const route = useRoute()
const act = ref({})
const loading = ref(false)
const error = ref('')
const owner = computed(() => ownsActivity(act.value, session.value))
const request = createApiClient({ baseUrl: import.meta.env.VITE_API_BASE_URL || '/api' })
let controller
let revision = 0

const fmtTime = (s) => (s ? String(s).replace('T', ' ') : '—')
const STATUS = {
  draft: { text: '草稿', type: 'info' },
  published: { text: '已发布', type: 'success' },
  ongoing: { text: '进行中', type: 'warning' },
  finished: { text: '已结束', type: 'primary' },
  cancelled: { text: '已取消', type: 'danger' },
}
const statusText = (s) => STATUS[s]?.text || s
const statusType = (s) => STATUS[s]?.type || 'info'

async function load() {
  controller?.abort()
  controller = new AbortController()
  const ticket = ++revision
  loading.value = true
  error.value = ''
  try {
    const data = await request(`/activities/${encodeURIComponent(route.params.id)}`, {
      signal: controller.signal, authRequired: false, allowBareResponse: true
    })
    if (ticket !== revision) return
    if (!data?.id) throw new Error('活动详情加载失败，请稍后重试')
    act.value = data
  } catch (cause) {
    if (ticket === revision && cause.name !== 'AbortError') error.value = cause.message
  } finally {
    if (ticket === revision) loading.value = false
  }
}
watch(() => route.params.id, () => { act.value = {}; load() }, { immediate: true })
onBeforeUnmount(() => { ++revision; controller?.abort() })
</script>

<style scoped>
.detail-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.detail-head h2{margin:0}
</style>
