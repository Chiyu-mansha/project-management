<template>
  <div class="account-page">
    <h2 class="page-title">账号管理</h2>

    <el-empty v-if="!session" description="请先登录">
      <el-button type="primary" @click="$router.push('/login')">去登录</el-button>
    </el-empty>

    <template v-else>
      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="mb" />

      <!-- 当前账号 -->
      <el-card class="section" shadow="never">
        <div class="current-head">
          <div class="avatar-wrap">
            <el-avatar :size="72" :src="avatarUrl(me?.avatar)" class="avatar">{{ initial(me?.name) }}</el-avatar>
            <label class="avatar-upload">
              <input type="file" accept="image/*" hidden @change="onAvatarFile" />
              <el-button size="small" :loading="uploading">更换头像</el-button>
            </label>
          </div>
          <div class="current-info">
            <div class="name-row">
              <span class="name">{{ me?.name || '未命名' }}</span>
              <el-tag :type="me?.role === 'student' ? 'primary' : 'success'" size="small">
                {{ me?.role === 'student' ? '学生' : '发布者' }}
              </el-tag>
              <el-tag v-if="me?.current !== false" type="info" size="small">当前</el-tag>
            </div>
            <div class="meta">账号：{{ me?.account }}</div>
            <div class="meta" v-if="me?.major">专业：{{ me?.major }} · 年级：{{ me?.grade }}</div>
            <div class="meta" v-if="me?.organization">组织：{{ me?.organization }}</div>
          </div>
        </div>
      </el-card>

      <!-- 基本信息 -->
      <el-card class="section" shadow="never">
        <template #header><span class="card-title">基本信息</span></template>
        <el-skeleton v-if="loading" :rows="4" animated />
        <el-form v-else :model="form" label-width="110px" @submit.prevent="saveBasic">
          <el-form-item label="姓名">
            <el-input v-model="form.name" />
          </el-form-item>
          <template v-if="session?.role === 'student'">
            <el-form-item label="专业"><el-input v-model="form.major" /></el-form-item>
            <el-form-item label="年级"><el-input v-model="form.grade" /></el-form-item>
            <el-form-item label="兴趣"><el-input v-model="form.interests" placeholder="逗号分隔" /></el-form-item>
            <el-form-item label="技能"><el-input v-model="form.skills" placeholder="逗号分隔" /></el-form-item>
            <el-form-item label="需要综测积分">
              <el-switch v-model="form.need_comprehensive_score" :active-value="1" :inactive-value="0" />
            </el-form-item>
            <el-form-item label="需要操行分">
              <el-switch v-model="form.need_conduct_score" :active-value="1" :inactive-value="0" />
            </el-form-item>
            <el-form-item label="需要创新分">
              <el-switch v-model="form.need_innovation_score" :active-value="1" :inactive-value="0" />
            </el-form-item>
          </template>
          <template v-else>
            <el-form-item label="组织"><el-input v-model="form.organization" /></el-form-item>
          </template>
          <el-form-item>
            <el-button type="primary" native-type="submit" :loading="saving">保存</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 修改密码 -->
      <el-card class="section" shadow="never">
        <template #header><span class="card-title">修改密码</span></template>
        <el-form :model="pwd" label-width="110px" @submit.prevent="savePassword">
          <el-form-item label="旧密码">
            <el-input v-model="pwd.old_password" type="password" show-password />
          </el-form-item>
          <el-form-item label="新密码">
            <el-input v-model="pwd.new_password" type="password" show-password />
          </el-form-item>
          <el-form-item label="确认新密码">
            <el-input v-model="pwd.confirm" type="password" show-password />
          </el-form-item>
          <el-form-item>
            <el-button type="primary" native-type="submit" :loading="savingPwd">修改密码</el-button>
          </el-form-item>
        </el-form>
      </el-card>

      <!-- 多账号切换 -->
      <el-card class="section" shadow="never">
        <template #header><span class="card-title">我的账号（可切换）</span></template>
        <el-skeleton v-if="loadingList" :rows="3" animated />
        <div v-else class="account-list">
          <div v-for="acc in accounts" :key="acc.role + acc.id" class="account-item" :class="{ current: acc.current }">
            <el-avatar :size="44" :src="avatarUrl(acc.avatar)" class="acc-avatar">{{ initial(acc.name) }}</el-avatar>
            <div class="acc-info">
              <div class="acc-name">
                {{ acc.name }}
                <el-tag size="small" :type="acc.role === 'student' ? 'primary' : 'success'">
                  {{ acc.role === 'student' ? '学生' : '发布者' }}
                </el-tag>
                <el-tag v-if="acc.current" size="small" type="info">当前</el-tag>
              </div>
              <div class="acc-meta">账号：{{ acc.account }}</div>
              <div class="acc-meta" v-if="acc.major">专业：{{ acc.major }} · 年级：{{ acc.grade }}</div>
              <div class="acc-meta" v-if="acc.organization">组织：{{ acc.organization }}</div>
            </div>
            <div class="acc-actions">
              <el-button v-if="!acc.current" type="primary" size="small" :loading="switching === (acc.role + acc.id)" @click="switchTo(acc)">
                切换
              </el-button>
              <el-button v-else size="small" disabled>当前账号</el-button>
            </div>
          </div>
          <el-empty v-if="accounts.length === 0" description="暂无其他账号" />
        </div>
      </el-card>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createApiClient } from '../api/request.js'
import { createAccountApi } from '../api/account.js'
import { session, setSession, clearSession } from '../auth/session.js'

const router = useRouter()
const API = import.meta.env.VITE_API_BASE_URL || '/api'

const request = createApiClient({
  baseUrl: API,
  getToken: () => session.value?.token,
  onUnauthorized: () => clearSession()
})
const accountApi = createAccountApi(request)

const loading = ref(false)
const loadingList = ref(false)
const saving = ref(false)
const savingPwd = ref(false)
const uploading = ref(false)
const switching = ref('')
const error = ref('')

const me = ref(null)
const accounts = ref([])

const FIELDS = ['name', 'major', 'grade', 'interests', 'skills', 'organization',
  'need_comprehensive_score', 'need_conduct_score', 'need_innovation_score']

const form = reactive(Object.fromEntries(FIELDS.map((k) => [k, k.startsWith('need_') ? 0 : ''])))
const pwd = reactive({ old_password: '', new_password: '', confirm: '' })

function avatarUrl(url) {
  if (!url) return ''
  if (url.startsWith('http') || url.startsWith('/')) return url
  return url
}
function initial(name) {
  return (name || '?').trim().charAt(0) || '?'
}

function applyMe(data) {
  me.value = data
  FIELDS.forEach((k) => {
    form[k] = data?.[k] ?? (k.startsWith('need_') ? 0 : '')
  })
}

async function loadMe() {
  loading.value = true
  error.value = ''
  try {
    applyMe(await accountApi.me())
  } catch (cause) {
    error.value = cause.message
  } finally {
    loading.value = false
  }
}

async function loadAccounts() {
  loadingList.value = true
  try {
    const data = await accountApi.list()
    accounts.value = data?.items || []
  } catch (cause) {
    error.value = cause.message
  } finally {
    loadingList.value = false
  }
}

async function saveBasic() {
  if (saving.value) return
  saving.value = true
  error.value = ''
  try {
    const body = Object.fromEntries(FIELDS.map((k) => [k, form[k]]))
    applyMe(await accountApi.updateBasic(body))
    ElMessage.success('已保存')
    await loadAccounts()
  } catch (cause) {
    error.value = cause.message
  } finally {
    saving.value = false
  }
}

async function savePassword() {
  if (savingPwd.value) return
  if (!pwd.old_password || !pwd.new_password) {
    ElMessage.warning('请填写完整')
    return
  }
  if (pwd.new_password.length < 6) {
    ElMessage.warning('新密码至少 6 位')
    return
  }
  if (pwd.new_password !== pwd.confirm) {
    ElMessage.warning('两次新密码不一致')
    return
  }
  savingPwd.value = true
  error.value = ''
  try {
    await accountApi.changePassword({ old_password: pwd.old_password, new_password: pwd.new_password })
    ElMessage.success('密码已修改')
    pwd.old_password = ''
    pwd.new_password = ''
    pwd.confirm = ''
  } catch (cause) {
    error.value = cause.message
  } finally {
    savingPwd.value = false
  }
}

async function onAvatarFile(event) {
  const file = event.target.files?.[0]
  event.target.value = ''
  if (!file) return
  uploading.value = true
  error.value = ''
  try {
    const formData = new FormData()
    formData.append('file', file)
    const token = session.value?.token
    const res = await fetch(`${API}/upload`, {
      method: 'POST',
      headers: token ? { Authorization: `Bearer ${token}` } : {},
      body: formData
    })
    const result = await res.json()
    if (result?.code !== 0) throw new Error(result?.message || '上传失败')
    await accountApi.updateAvatar(result.data.url)
    await loadMe()
    ElMessage.success('头像已更新')
  } catch (cause) {
    error.value = cause.message
  } finally {
    uploading.value = false
  }
}

async function switchTo(acc) {
  const key = acc.role + acc.id
  switching.value = key
  error.value = ''
  try {
    const data = await accountApi.switchAccount({ role: acc.role, id: acc.id })
    setSession(data)
    ElMessage.success('已切换账号')
    router.push(acc.role === 'organizer' ? '/browse' : '/')
  } catch (cause) {
    error.value = cause.message
  } finally {
    switching.value = ''
  }
}

onMounted(() => {
  if (session.value) {
    loadMe()
    loadAccounts()
  }
})
</script>

<style scoped>
.account-page { max-width: 760px; margin: 0 auto; }
.page-title { margin: 0 0 16px; }
.mb { margin-bottom: 12px; }
.section { margin-bottom: 16px; }
.card-title { font-weight: 600; }
.current-head { display: flex; gap: 20px; align-items: center; }
.avatar-wrap { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.avatar { background: #eaf1fb; color: #3a67a8; }
.current-info { flex: 1; }
.name-row { display: flex; align-items: center; gap: 8px; font-size: 18px; font-weight: 600; margin-bottom: 6px; }
.meta { color: #6b7280; font-size: 13px; margin-top: 2px; }
.account-list { display: flex; flex-direction: column; gap: 12px; }
.account-item { display: flex; gap: 12px; align-items: center; padding: 12px; border: 1px solid #eef1f6; border-radius: 10px; }
.account-item.current { background: #f3f7ff; border-color: #c7d7f5; }
.acc-avatar { background: #eaf1fb; color: #3a67a8; }
.acc-info { flex: 1; }
.acc-name { display: flex; align-items: center; gap: 6px; font-weight: 600; margin-bottom: 2px; }
.acc-meta { color: #6b7280; font-size: 12px; }
.acc-actions { flex-shrink: 0; }
</style>
