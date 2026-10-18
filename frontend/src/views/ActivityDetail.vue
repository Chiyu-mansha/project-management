<template>
  <div>
    <div class="detail-head">
      <h2>{{ act.title || '加载中…' }}</h2>
      <div>
        <el-button type="success" @click="genDlg = true">✨ AI 生成推文</el-button>
        <el-button type="warning" @click="$router.push(`/activities/${act.id}/edit`)">编辑</el-button>
        <el-button @click="$router.push('/activities')">返回列表</el-button>
      </div>
    </div>

    <el-descriptions :column="2" border>
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

    <el-dialog v-model="genDlg" title="✨ AI 生成推文" width="640px">
      <div class="gen-bar">
        <span>风格：</span>
        <el-radio-group v-model="genStyle" size="small">
          <el-radio-button label="简约" /><el-radio-button label="活泼" /><el-radio-button label="正式" />
        </el-radio-group>
        <el-button type="primary" size="small" :loading="genLoading" @click="generate">生成</el-button>
      </div>
      <el-input v-model="genContent" type="textarea" :rows="12" placeholder="点击「生成」，AI 会基于活动信息生成推文，可手动二次编辑…" />
      <template #footer>
        <el-button @click="copyGen">复制</el-button>
        <el-button type="primary" @click="genDlg = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'

const API = 'http://localhost:8000'
const route = useRoute()
const act = ref({})

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

// AI 推文生成
const genDlg = ref(false)
const genStyle = ref('简约')
const genContent = ref('')
const genLoading = ref(false)

const generate = async () => {
  genLoading.value = true
  try {
    const d = await (await fetch(`${API}/api/activities/${route.params.id}/generate-article`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ style: genStyle.value }),
    })).json()
    genContent.value = d.data?.content || ''
  } finally {
    genLoading.value = false
  }
}

const copyGen = async () => {
  try { await navigator.clipboard.writeText(genContent.value); ElMessage.success('已复制') }
  catch { ElMessage.error('复制失败') }
}

onMounted(async () => {
  const d = await (await fetch(`${API}/api/activities/${route.params.id}`)).json()
  act.value = d.data
})
</script>

<style scoped>
.detail-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.detail-head h2{margin:0}
.gen-bar{display:flex;align-items:center;gap:10px;margin-bottom:12px}
</style>
