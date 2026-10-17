<script setup>
import { ref } from 'vue'
import { createApiClient } from '../api/request.js'
import { session, setSession, clearSession } from './session.js'

const role = ref('student')
const userId = ref(1)
const loading = ref(false)
const error = ref('')
const request = createApiClient({ baseUrl: import.meta.env.VITE_API_BASE_URL || '/api' })
async function login() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const requested = { role: role.value, id: userId.value }
    const data = await request('/dev/token', { method: 'POST', body: requested, authRequired: false })
    setSession({ ...requested, token: data?.token })
  } catch (cause) {
    error.value = cause.message
  } finally {
    loading.value = false
  }
}
</script>

<template>
  <aside class="dev-session" aria-label="开发联调登录">
    <details>
      <summary>开发联调登录{{ session ? ` · ${session.role === 'student' ? '学生' : '发布者'} #${session.id}` : '' }}</summary>
      <p>使用后端已有用户 ID 获取开发凭证；此入口仅在 Vite 开发环境显示。</p>
      <form @submit.prevent="login">
        <el-select v-model="role" aria-label="联调身份" :disabled="loading" style="width:120px">
          <el-option label="学生" value="student" /><el-option label="发布者" value="organizer" />
        </el-select>
        <el-input-number v-model="userId" aria-label="已有用户 ID" :min="1" :precision="0" :disabled="loading" />
        <el-button native-type="submit" type="primary" :loading="loading">获取开发凭证</el-button>
        <el-button v-if="session" :disabled="loading" @click="clearSession">退出</el-button>
      </form>
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
    </details>
  </aside>
</template>

<style scoped>
.dev-session { max-width: 1352px; margin: 0 auto 16px; padding: 12px 24px; border: 1px dashed #b1b3b8; border-radius: 8px; background: #fff; }
summary { cursor: pointer; color: #606266; }
p { color: #606266; font-size: 14px; }
form { display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 12px; }
</style>
