<template>
  <div>
    <div class="detail-head">
      <h2>{{ act.title || (loading ? '加载中…' : '活动详情') }}</h2>
      <div>
        <el-button v-if="owner" type="success" @click="genDlg = true">✨ AI 生成推文</el-button>
        <el-button v-if="owner" type="primary" @click="$router.push(`/activities/${act.id}/checkins`)">签到核销</el-button>
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
      @session-expired="clearSession" @form-saved="load" @registration-submitted="onRegistrationChanged" @registration-cancelled="onRegistrationChanged" />
    <div v-if="act.id && session?.role === 'student'" class="checkin-card">
      <h3>现场签到</h3>
      <p v-if="!checkinState.registered">请先完成报名，报名通过后才能签到领取电子票。</p>
      <p v-else-if="checkinState.checked_in">已签到，凭证状态：{{ credentialLabel(checkinState.credential?.status) }}</p>
      <p v-else>你已报名该活动，可以签到并自动发放电子活动票。</p>
      <el-button type="primary" :disabled="!checkinState.registered || checkinState.checked_in" :loading="checkinLoading" @click="doCheckin">立即签到</el-button>
    </div>

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
import { createCredentialApi } from '../api/credentials.js'
import { session, clearSession } from '../auth/session.js'
import { ElMessage } from 'element-plus'
import { MdEditor, MdPreview } from 'md-editor-v3'
import 'md-editor-v3/lib/style.css'

// AI 推文走 vite 代理(127.0.0.1:8000),避免 Windows localhost 解析问题(PM 合并仪式整合)
const API = import.meta.env.VITE_API_BASE_URL || ''

const route = useRoute()
const act = ref({})
const loading = ref(false)
const error = ref('')
const owner = computed(() => ownsActivity(act.value, session.value))
const request = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  getToken: () => session.value?.token || '',
})
const credentialApi = createCredentialApi(request)
const checkinState = ref({ registered: false, checked_in: false, credential: null })
const checkinLoading = ref(false)
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
const credentialLabel = (value) => ({ issued: '已签到', confirmed: '已确认', signed: '已签章' }[value] || value || '已发放')

async function refreshCheckin() {
  if (session.value?.role !== 'student' || !act.value.id) {
    checkinState.value = { registered: false, checked_in: false, credential: null }
    return
  }
  try {
    checkinState.value = await credentialApi.checkinStatus(act.value.id)
  } catch {
    checkinState.value = { registered: false, checked_in: false, credential: null }
  }
}

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
    await refreshCheckin()
  } catch (cause) {
    if (ticket === revision && cause.name !== 'AbortError') error.value = cause.message
  } finally {
    if (ticket === revision) loading.value = false
  }
}

function onRegistrationChanged() {
  load()
}

async function doCheckin() {
  checkinLoading.value = true
  try {
    await credentialApi.checkin(act.value.id)
    ElMessage.success('签到成功，电子票已发放')
    await refreshCheckin()
  } catch (e) {
    ElMessage.error(e.message || '签到失败')
  } finally {
    checkinLoading.value = false
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
    const d = await (await fetch(`${API}/api/activities/${route.params.id}/generate-article`, {
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
    const d = await (await fetch(`${API}/api/activities/${route.params.id}/polish-article`, {
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
    const r = await fetch(`${API}/api/upload`, { method: 'POST', body: fd })
    const d = await r.json()
    return `${API}${d.data?.url || ''}`
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
    const r = await fetch(`${API}/api/activities/${route.params.id}`, {
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
.article-card{margin-top:16px;background:#fff;border-radius:16px;padding:32px 40px 28px;box-shadow:0 4px 20px rgba(0,0,0,.08)}
.article-card :deep(h1){text-align:center;font-size:24px;font-weight:800;margin:22px 0 12px;color:#1f2937;line-height:1.4}
.article-card :deep(h2){text-align:center;font-size:18px;font-weight:700;margin:24px 0 14px;color:#303133}
.article-card :deep(h3){font-size:16px;font-weight:700;color:#3a5bff;margin:18px 0 10px}
.article-card :deep(p){line-height:1.9;margin:12px 0;color:#333;font-size:15px}
.article-card :deep(strong){color:#d4380d;font-weight:700}
.article-card :deep(blockquote){margin:16px 0;padding:16px 20px;background:#f7f8fb;border-radius:8px;color:#4b5563;font-size:15px}
.article-card :deep(img){max-width:100%;border-radius:12px;display:block;margin:16px auto;box-shadow:0 4px 16px rgba(0,0,0,.1)}
.article-card :deep(ul),.article-card :deep(ol){padding-left:22px;margin:10px 0}
.article-card :deep(li){margin:8px 0;line-height:1.7}
.article-card :deep(hr){border:none;height:1px;background:#e5e7eb;margin:24px 0}
.article-card :deep(code){background:#f5f5f5;border-radius:4px;padding:2px 6px;font-size:13px;color:#c7254e}
.checkin-card{margin-top:18px;padding:18px 20px;background:#f7f9fc;border-radius:12px}
.checkin-card h3{margin:0 0 8px;font-size:16px}
.checkin-card p{margin:0 0 12px;color:#56617a}
</style>
