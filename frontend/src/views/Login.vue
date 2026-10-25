<template>
  <div class="auth-page">
    <div class="auth-card">
      <h2 class="framed-title">登录</h2>
      <el-radio-group v-model="role" class="role-switch" @change="error = ''">
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
          <el-button link class="link-btn" @click="$router.push('/register')">没有账号？去注册</el-button>
        </div>
      </el-form>
    </div>
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
    const target = route.query.redirect || (role.value === 'organizer' ? '/browse' : '/')
    router.push(target)
  } catch (cause) {
    error.value = cause.message
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.auth-page{min-height:100vh;display:flex;align-items:center;justify-content:center;padding:40px 20px;background:#dce9f8}
.auth-card{width:100%;max-width:420px;padding:34px 36px 30px;border-radius:14px;background:#f2f2f2;box-shadow:0 16px 40px rgba(60,88,130,.18)}
.framed-title{margin:0 0 22px;text-align:center;color:#1d2229;font-size:26px;font-weight:800;letter-spacing:6px;text-indent:6px}
.role-switch{margin-bottom:6px}
.auth-form{width:100%;margin-top:14px}
.actions{display:flex;align-items:center;gap:12px}
.link-btn{font-weight:600}
@media(max-width:480px){.auth-card{padding:26px 20px 22px}}
</style>
