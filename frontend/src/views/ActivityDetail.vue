<template>
  <div>
    <div class="detail-head">
      <h2>{{ act.title || '加载中…' }}</h2>
      <div>
        <el-button type="warning" @click="$router.push(`/activities/${act.id}/edit`)">编辑</el-button>
        <el-button @click="$router.push('/activities')">返回列表</el-button>
      </div>
    </div>

    <el-descriptions :column="2" border>
      <el-descriptions-item label="类型">{{ act.type || '-' }}</el-descriptions-item>
      <el-descriptions-item label="状态">
        <el-tag :type="statusType(act.status)">{{ statusText(act.status) }}</el-tag>
      </el-descriptions-item>
      <el-descriptions-item label="主办方">{{ act.organizer || '-' }}</el-descriptions-item>
      <el-descriptions-item label="地点">{{ act.location || '-' }}</el-descriptions-item>
      <el-descriptions-item label="开始时间">{{ fmtTime(act.start_time) }}</el-descriptions-item>
      <el-descriptions-item label="结束时间">{{ fmtTime(act.end_time) }}</el-descriptions-item>
      <el-descriptions-item label="报名截止">{{ fmtTime(act.signup_deadline) }}</el-descriptions-item>
      <el-descriptions-item label="人数上限">{{ act.max_participants ?? '不限' }}</el-descriptions-item>
      <el-descriptions-item label="电子票">{{ act.has_ticket ? '是' : '否' }}</el-descriptions-item>
      <el-descriptions-item label="综测加分">{{ act.zongce_score || '-' }}</el-descriptions-item>
      <el-descriptions-item label="标签">{{ act.tags || '-' }}</el-descriptions-item>
      <el-descriptions-item label="简介" :span="2">{{ act.description || '-' }}</el-descriptions-item>
    </el-descriptions>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'

const API = 'http://localhost:8000'
const route = useRoute()
const act = ref({})

const fmtTime = (s) => (s ? String(s).replace('T', ' ') : '—')
const statusText = (s) => ({ draft: '草稿', published: '已发布', cancelled: '已取消' }[s] || s)
const statusType = (s) => ({ draft: 'info', published: 'success', cancelled: 'danger' }[s] || 'info')

onMounted(async () => {
  const d = await (await fetch(`${API}/api/activities/${route.params.id}`)).json()
  act.value = d
})
</script>

<style scoped>
.detail-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.detail-head h2{margin:0}
</style>
