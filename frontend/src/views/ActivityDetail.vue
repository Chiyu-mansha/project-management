<template>
  <div>
    <div class="detail-head">
      <h2>{{ act.title || (loading ? '加载中…' : '活动详情') }}</h2>
      <div>
        <el-button v-if="owner" type="success" @click="genDlg = true">✨ AI 生成推文</el-button>
        <el-button v-if="owner" type="warning" @click="$router.push(`/activities/${act.id}/edit`)">编辑</el-button>
        <el-button @click="$router.push(session?.role === 'organizer' ? '/activities' : '/browse')">返回列表</el-button>
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
    <div v-if="act.article" class="article-card">
      <MdPreview :modelValue="act.article" />
    </div>
    <ActivityRegistrationActions v-if="act.id" :activity="act" :session="session"
      @session-expired="clearSession" @form-saved="load" @registration-submitted="load" @registration-cancelled="load" />

    <el-dialog v-model="genDlg" title="✨ AI 生成推文" width="860px">
      <div class="gen-bar">
        <span>风格：</span>
        <el-radio-group v-model="genStyle" size="small">
          <el-radio-button label="简约" /><el-radio-button label="活泼" /><el-radio-button label="正式" />
        </el-radio-group>
        <el-button type="primary" size="small" :loading="genLoading" @click="generate">生成</el-button>
        <el-button type="warning" size="small" :loading="genLoading" @click="polish">润色</el-button>
      </div>
      <MdEditor v-model="genContent" :on-upload-img="onUploadImg" style="height: 400px" />
      <template #footer>
        <el-button @click="copyGen">复制</el-button>
        <el-button type="success" :loading="saveLoading" @click="saveArticle">保存推文</el-button>
        <el-button type="primary" @click="genDlg = false">关闭</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { useRoute } from 'vue-router'
import ActivityRegistrationActions from '../domain/ActivityRegistrationActions.vue'
import { ownsActivity } from '../domain/activityAccess.js'
import { createApiClient } from '../api/request.js'
import { session, clearSession } from '../auth/session.js'
import { ElMessage } from 'element-plus'
import { MdEditor, MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'

// AI 推文走 vite 代理(127.0.0.1:8000),避免 Windows localhost 解析问题(PM 合并仪式整合)
const API = import.meta.env.VITE_API_BASE_URL || '/api'
const ASSET_BASE = API.replace(/\/api\/?$/, '')

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

// AI 推文生成(POD-1)
const genDlg = ref(false)
const genStyle = ref('简约')
const genContent = ref('')
const genLoading = ref(false)

const generate = async () => {
  genLoading.value = true
  try {
    const d = await (await fetch(`${API}/activities/${route.params.id}/generate-article`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ style: genStyle.value }),
    })).json()
    genContent.value = d.data?.content || ''
  } finally {
    genLoading.value = false
  }
}

const polish = async () => {
  if (!genContent.value) return ElMessage.warning('先点「生成」再润色')
  genLoading.value = true
  try {
    const d = await (await fetch(`${API}/activities/${route.params.id}/polish-article`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content: genContent.value, style: genStyle.value }),
    })).json()
    genContent.value = d.data?.content || genContent.value
  } finally {
    genLoading.value = false
  }
}

const onUploadImg = async (files, callback) => {
  const urls = await Promise.all(files.map(async (file) => {
    const fd = new FormData()
    fd.append('file', file)
    const r = await fetch(`${API}/upload`, { method: 'POST', body: fd })
    const d = await r.json()
    return `${ASSET_BASE}${d.data?.url || ''}`
  }))
  callback(urls)
}

const copyGen = async () => {
  try { await navigator.clipboard.writeText(genContent.value); ElMessage.success('已复制') }
  catch { ElMessage.error('复制失败') }
}

const saveLoading = ref(false)
const saveArticle = async () => {
  if (!genContent.value) return ElMessage.warning('先点「生成」再保存')
  saveLoading.value = true
  try {
    const r = await fetch(`${API}/activities/${route.params.id}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ...act.value, article: genContent.value }),
    })
    if (!r.ok) {
      const e = await r.json().catch(() => ({}))
      return ElMessage.error(e.message || '保存失败')
    }
    ElMessage.success('推文已保存')
    act.value.article = genContent.value
  } finally {
    saveLoading.value = false
  }
}
</script>

<style scoped>
.detail-head{display:flex;justify-content:space-between;align-items:center;margin-bottom:16px}
.detail-head h2{margin:0}
.gen-bar{display:flex;align-items:center;gap:10px;margin-bottom:12px}
.article-card{margin-top:16px;background:#fff;border-radius:16px;padding:32px 40px 28px;box-shadow:0 4px 20px rgba(0,0,0,.08);position:relative;overflow:hidden}
.article-card::before{content:'';position:absolute;top:0;left:0;right:0;height:5px;background:linear-gradient(90deg,#3a5bff,#8b5cf6,#ec4899)}
/* 微信文章风格 */
.article-card :deep(h1){text-align:center;font-size:24px;font-weight:800;margin:22px 0 12px;color:#1f2937;line-height:1.4}
.article-card :deep(h2){text-align:center;font-size:18px;font-weight:700;margin:24px 0 14px;color:#303133;position:relative}
.article-card :deep(h2)::after{content:'';display:block;width:40px;height:3px;margin:8px auto 0;background:linear-gradient(90deg,#3a5bff,#8b5cf6);border-radius:2px}
.article-card :deep(h3){font-size:16px;font-weight:700;color:#3a5bff;border-left:4px solid #3a5bff;padding-left:10px;margin:18px 0 10px}
.article-card :deep(p){line-height:1.9;margin:12px 0;color:#333;font-size:15px}
.article-card :deep(strong){color:#d4380d;font-weight:700}
.article-card :deep(blockquote){margin:16px 0;padding:16px 20px;background:linear-gradient(135deg,#eef2ff,#f5f3ff);border-left:4px solid #3a5bff;border-radius:8px;color:#4b5563;font-size:15px}
.article-card :deep(img){max-width:100%;border-radius:12px;display:block;margin:16px auto;box-shadow:0 4px 16px rgba(0,0,0,.1)}
.article-card :deep(ul),.article-card :deep(ol){padding-left:22px;margin:10px 0}
.article-card :deep(li){margin:8px 0;line-height:1.7}
.article-card :deep(li)::marker{color:#3a5bff}
.article-card :deep(hr){border:none;height:1px;background:linear-gradient(90deg,transparent,#c7d2fe,transparent);margin:24px 0}
.article-card :deep(code){background:#f5f5f5;border-radius:4px;padding:2px 6px;font-size:13px;color:#c7254e}
</style>
