<template>
  <div class="profile-page">
    <div class="profile-header">
      <el-button v-if="!editing" @click="$router.push('/')">返回</el-button>
      <h2>我的画像</h2>
      <el-button v-if="student && !editing && loaded" type="primary" :disabled="loading || saving" @click="edit">编辑</el-button>
    </div>
    <el-empty v-if="!student" description="请先以学生身份登录">
      <el-button type="primary" @click="$router.push('/login')">去登录</el-button>
    </el-empty>
    <template v-else>
      <el-alert v-if="error" :title="error" type="error" show-icon :closable="false">
        <el-button v-if="!editing" :disabled="loading || saving" @click="load">重新加载</el-button>
      </el-alert>
      <el-skeleton v-if="loading || (saving && !editing)" :rows="6" animated />
      <el-form v-else-if="editing" class="profile-form" label-width="160px" @submit.prevent="saveProfile">
        <el-form-item v-for="(label, key) in PROFILE_LABELS" :key="key" :label="label">
          <el-switch v-if="key.startsWith('need_')" v-model="form[key]" :active-value="1" :inactive-value="0" :disabled="saving" />
          <el-input v-else v-model="form[key]" :disabled="saving" :placeholder="key === 'interests' || key === 'skills' ? '多个内容可用逗号分隔' : ''" />
        </el-form-item>
        <el-button type="primary" native-type="submit" :loading="saving">保存</el-button>
      </el-form>
      <template v-else-if="loaded">
        <el-descriptions :column="1" border class="profile-form">
          <el-descriptions-item v-for="(label, key) in PROFILE_LABELS" :key="key" :label="label">
            {{ key.startsWith('need_') ? (profile[key] === 1 ? '是' : '否') : (profile[key] || '未填写') }}
          </el-descriptions-item>
        </el-descriptions>
        <el-button class="recommend-link" @click="$router.push('/recommend')">查看推荐</el-button>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onBeforeUnmount, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { createApiClient } from '../api/request.js'
import { createProfileApi } from '../api/profile.js'
import { session, clearSession } from '../auth/session.js'
import { PROFILE_LABELS, useProfile } from '../domain/profile.js'

const student = computed(() => session.value?.role === 'student')
const request = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  getToken: () => session.value?.token,
  onUnauthorized: clearSession
})
const { form, profile, editing, loaded, loading, saving, error, reset, load, edit, save } = useProfile(
  createProfileApi(request), () => student.value ? session.value.id : null
)
async function saveProfile() {
  if (await save()) ElMessage.success('画像已保存')
}
watch(() => [session.value?.token, session.value?.id, session.value?.role], () => {
  reset()
  if (student.value) load()
}, { immediate: true })
onBeforeUnmount(reset)
</script>

<style scoped>
.profile-page{max-width:640px}
.profile-header{display:flex;align-items:center;gap:16px;min-height:48px}
.profile-header h2{flex:1;margin:0}
.profile-form{margin-top:16px}
.recommend-link{margin-top:20px}
</style>
