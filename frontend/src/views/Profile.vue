<template>
  <div class="profile-page">
    <h2>我的画像</h2>
    <el-empty v-if="!student" description="请先以学生身份登录">
      <el-button type="primary" @click="$router.push('/login')">去登录</el-button>
    </el-empty>
    <template v-else>
      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" />
      <el-skeleton v-if="loading" :rows="6" animated />
      <el-form v-else class="profile-form" label-width="140px" @submit.prevent="save">
        <el-form-item label="专业"><el-input v-model="form.major" /></el-form-item>
        <el-form-item label="年级"><el-input v-model="form.grade" /></el-form-item>
        <el-form-item label="兴趣"><el-input v-model="form.interests" placeholder="逗号分隔，如：算法,竞赛" /></el-form-item>
        <el-form-item label="技能"><el-input v-model="form.skills" placeholder="逗号分隔，如：Python" /></el-form-item>
        <el-form-item label="需要综合素养评定积分">
          <el-switch v-model="form.need_comprehensive_score" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="需要操行分">
          <el-switch v-model="form.need_conduct_score" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-form-item label="需要创新分">
          <el-switch v-model="form.need_innovation_score" :active-value="1" :inactive-value="0" />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="saving">保存</el-button>
      </el-form>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createApiClient } from '../api/request.js'
import { createProfileApi } from '../api/profile.js'
import { session, clearSession } from '../auth/session.js'

const FIELDS = ['major', 'grade', 'interests', 'skills', 'need_comprehensive_score', 'need_conduct_score', 'need_innovation_score']

const request = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  getToken: () => session.value?.token,
  onUnauthorized: () => clearSession()
})
const profileApi = createProfileApi(request)
const student = computed(() => session.value?.role === 'student')
const loading = ref(false)
const saving = ref(false)
const error = ref('')
const form = reactive(Object.fromEntries(FIELDS.map((k) => [k, ''])))

function apply(data) {
  FIELDS.forEach((k) => { form[k] = data?.[k] ?? (k.startsWith('need_') ? 0 : '') })
}

async function load() {
  if (!student.value) return
  loading.value = true
  error.value = ''
  try {
    apply(await profileApi.getProfile(session.value.id))
  } catch (cause) {
    error.value = cause.message
  } finally {
    loading.value = false
  }
}

async function save() {
  if (saving.value || !student.value) return
  saving.value = true
  error.value = ''
  try {
    const body = Object.fromEntries(FIELDS.map((k) => [k, form[k]]))
    apply(await profileApi.updateProfile(session.value.id, body))
    ElMessage.success('画像已保存')
  } catch (cause) {
    error.value = cause.message
  } finally {
    saving.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.profile-page{max-width:520px}
.profile-form{margin-top:16px}
</style>
