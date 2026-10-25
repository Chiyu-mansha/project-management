<template>
  <div class="auth-page">
    <h2>登录</h2>
    <el-radio-group v-model="role" @change="error = ''">
      <el-radio-button value="student">学生</el-radio-button>
      <el-radio-button value="organizer">发布者</el-radio-button>
    </el-radio-group>
    <el-form class="auth-form" label-width="90px" @submit.prevent="submit">
      <el-form-item :label="role === 'student' ? '学号' : '工号'">
        <el-input v-model="account" :placeholder="role === 'student' ? '请输入学号' : '请输入工号'" />
      </el-form-item>
      <el-form-item label="密码">
        <el-input v-model="password" type="password" show-password placeholder="请输入密码" />
      </el-form-item>
      <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
      <div class="actions">
        <el-button type="primary" native-type="submit" :loading="loading">登录</el-button>
        <el-button link @click="$router.push('/register')">没有账号？去注册</el-button>
      </div>
    </el-form>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createApiClient } from '../api/request.js'
import { createAuthApi } from '../api/auth.js'
import { setSession } from '../auth/session.js'

const router = useRouter()
const route = useRoute()
const request = createApiClient({ baseUrl: import.meta.env.VITE_API_BASE_URL || '/api' })
const auth = createAuthApi(request)
const role = ref('student')
const account = ref('')
const password = ref('')
const loading = ref(false)
const error = ref('')

async function submit() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const data = await auth.login({ role: role.value, account: account.value.trim(), password: password.value })
    setSession(data)
    ElMessage.success('登录成功')
    router.push(route.query.redirect || '/')
  } catch (cause) {
    error.value = cause.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page{max-width:420px;margin:40px auto}
.auth-form{margin-top:20px}
.actions{display:flex;align-items:center;gap:12px}
</style>
