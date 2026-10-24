<script setup>
import { computed, ref, watch, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { session, clearSession } from './auth/session.js'
import { createApiClient } from './api/request'
import { createNotificationApi } from './api/notifications'

const router = useRouter()
const route = useRoute()
const isAuthPage = computed(() => route.path === '/login' || route.path === '/register')
function logout() { clearSession(); router.push('/') }

// --- 未读消息逻辑 ---
const unreadCount = ref(0)
const request = createApiClient({ getToken: () => session.value?.token || '' })
const api = createNotificationApi(request)

async function fetchUnread() {
  if (!session.value) {
    unreadCount.value = 0
    return
  }
  try {
    const data = await api.unreadCount()
    unreadCount.value = data.count
  } catch (e) {
    // 忽略错误
  }
}

// 监听路由变化，每次切换页面刷新一下未读数
watch(() => route.path, () => {
  fetchUnread()
})
onMounted(fetchUnread)
</script>

<template>
  <div class="page">
    <template v-if="!isAuthPage">
    <header class="app-header"><h1>校园活动智能通知&amp;报名助理</h1></header>
    <nav class="topbar">
      <el-button link @click="$router.push('/')">🏠 首页</el-button>
      <el-button link @click="$router.push('/browse')">🎉 活动广场</el-button>
      <el-button v-if="session?.role === 'organizer'" link @click="$router.push('/activities')">📅 活动发布</el-button>
      <el-button v-if="session?.role === 'student'" link @click="$router.push('/recommend')">🎯 智能推荐</el-button>
      <el-button v-if="session?.role === 'student'" link @click="$router.push('/profile')">👤 我的画像</el-button>
      <el-button link @click="$router.push('/registrations')">📝 报名管理</el-button>
      <el-button link @click="$router.push('/faqs')">📚 FAQ 知识库</el-button>
      <el-button link @click="$router.push('/qa')">💬 智能答疑</el-button>
      <el-badge :value="unreadCount" :hidden="unreadCount === 0" :max="99">
        <el-button link @click="$router.push('/notifications')">🔔 通知中心</el-button>
      </el-badge>
      <span v-if="session" class="session-info">{{ session.role === 'student' ? '学生' : '发布者' }} #{{ session.id }}</span>
      <el-button v-if="!session" link type="primary" @click="$router.push('/login')">🔑 登录</el-button>
      <el-button v-else link @click="logout">退出</el-button>
    </nav>
    </template>
    <main :class="{panel: $route.path !== '/' && !isAuthPage}"><router-view /></main>
  </div>
</template>

<style scoped>
.page{min-height:100vh;background:linear-gradient(180deg,#f0f5ff 0%,#f7f9fc 320px,#f7f9fc 100%)}
.app-header{border-bottom:1px solid #ebeef5;padding:16px 24px;background:#fff}
.app-header h1{max-width:1400px;margin:0 auto;color:#303133;font-size:22px}
.topbar{max-width:1400px;margin:0 auto;display:flex;align-items:center;gap:12px;padding:14px 24px}
.session-info{margin-left:auto;color:#909399;font-size:13px}
.panel{max-width:1400px;margin:0 auto;background:#fff;border-radius:12px;padding:18px;box-shadow:0 4px 16px rgba(0,0,0,.06);margin-bottom:24px}
</style>
