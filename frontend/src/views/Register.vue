<template>
  <div class="auth-page">
    <div class="auth-card">
      <h2 class="framed-title">注册</h2>
      <el-radio-group v-model="role" class="role-switch" @change="error = ''">
        <el-radio-button value="student">学生</el-radio-button>
        <el-radio-button value="organizer">发布者</el-radio-button>
      </el-radio-group>
      <el-form class="auth-form" label-width="90px" @submit.prevent="submit">
        <template v-if="role === 'student'">
          <el-form-item label="学号"><el-input v-model="form.student_id" placeholder="请输入学号" /></el-form-item>
          <el-form-item label="姓名"><el-input v-model="form.name" placeholder="请输入真实姓名" /></el-form-item>
          <el-form-item label="专业"><el-input v-model="form.major" placeholder="选填" /></el-form-item>
          <el-form-item label="年级"><el-input v-model="form.grade" placeholder="选填" /></el-form-item>
        </template>
        <template v-else>
          <el-form-item label="工号"><el-input v-model="form.account" placeholder="请输入工号" /></el-form-item>
          <el-form-item label="姓名"><el-input v-model="form.name" placeholder="请输入姓名" /></el-form-item>
          <el-form-item label="组织"><el-input v-model="form.organization" placeholder="选填" /></el-form-item>
        </template>
        <el-form-item label="密码">
          <el-input v-model="form.password" type="password" show-password placeholder="请输入密码" />
        </el-form-item>
        <el-alert v-if="error" :title="error" type="error" :closable="false" show-icon />
        <div class="actions">
          <el-button type="primary" native-type="submit" :loading="loading">注册</el-button>
          <el-button link class="link-btn" @click="$router.push('/login')">已有账号？去登录</el-button>
        </div>
      </el-form>
    </div>
  </div>
</template>

<script setup>
import { reactive, ref } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createApiClient } from '../api/request.js'
import { createAuthApi } from '../api/auth.js'

const router = useRouter()
const request = createApiClient({ baseUrl: import.meta.env.VITE_API_BASE_URL || '/api' })
const auth = createAuthApi(request)
const role = ref('student')
const form = reactive({ student_id: '', name: '', major: '', grade: '', account: '', organization: '', password: '' })
const loading = ref(false)
const error = ref('')

async function submit() {
  if (loading.value) return
  loading.value = true
  error.value = ''
  try {
    const body = role.value === 'student'
      ? { role: 'student', student_id: form.student_id.trim(), name: form.name.trim(), major: form.major.trim(), grade: form.grade.trim(), password: form.password }
      : { role: 'organizer', account: form.account.trim(), name: form.name.trim(), organization: form.organization.trim(), password: form.password }
    await auth.register(body)
    ElMessage.success('注册成功，请登录')
    router.push('/login')
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
