<script setup>
import { computed } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { session, clearSession } from './auth/session.js'
const router = useRouter()
const route = useRoute()
const isAuthPage = computed(() => route.path === '/login' || route.path === '/register')
function logout() { clearSession(); router.push('/') }
</script>

<template>
  <div class="page">
    <template v-if="!isAuthPage && session?.role === 'organizer'">
      <div class="org-layout">
        <aside class="org-sidebar">
          <div class="org-brand">校园活动助手</div>
          <nav class="org-menu">
            <button :class="{ active: route.path === '/browse' }" @click="router.push('/browse')"><span class="ico">🎉</span><span>活动广场</span></button>
            <button :class="{ active: route.path.startsWith('/activities') }" @click="router.push('/activities')"><span class="ico">📅</span><span>活动发布</span></button>
            <button :class="{ active: route.path.startsWith('/registrations') }" @click="router.push('/registrations')"><span class="ico">📝</span><span>报名管理</span></button>
            <button :class="{ active: route.path === '/faqs' }" @click="router.push('/faqs')"><span class="ico">📚</span><span>FAQ 知识库</span></button>
            <button :class="{ active: route.path.startsWith('/notifications') }" @click="router.push('/notifications')"><span class="ico">🔔</span><span>通知中心</span></button>
            <button :class="{ active: route.path === '/account' }" @click="router.push('/account')"><span class="ico">👤</span><span>账号管理</span></button>
          </nav>
          <div class="org-bottom">
            <button @click="logout"><span class="ico">↩</span><span>退出</span></button>
          </div>
        </aside>
        <main class="org-content"><router-view /></main>
      </div>
    </template>
    <template v-else>
      <template v-if="!isAuthPage">
        <header class="app-header"><h1>校园活动智能通知&amp;报名助理</h1></header>
        <nav class="topbar">
          <el-button link @click="$router.push('/')">🏠 首页</el-button>
          <el-button link @click="$router.push('/browse')">🎉 活动广场</el-button>
          <el-button v-if="session?.role === 'student'" link @click="$router.push('/recommend')">🎯 智能推荐</el-button>
          <el-button v-if="session?.role === 'student'" link @click="$router.push('/profile')">👤 我的画像</el-button>
          <el-button link @click="$router.push('/registrations')">📝 报名管理</el-button>
          <el-button v-if="session?.role === 'student'" link @click="$router.push('/qa')">💬 智能答疑</el-button>
          <el-button link @click="$router.push('/notifications')">🔔 通知中心</el-button>
          <el-button v-if="session?.role === 'student'" link @click="$router.push('/account')">账号管理</el-button>
          <el-button v-if="!session" link type="primary" @click="$router.push('/login')">🔑 登录</el-button>
          <el-button v-else link @click="logout">退出</el-button>
        </nav>
      </template>
      <main :class="{panel: $route.path !== '/' && !isAuthPage}"><router-view /></main>
    </template>
  </div>
</template>

<style scoped>
.page{min-height:100vh;background:linear-gradient(180deg,#f0f5ff 0%,#f7f9fc 320px,#f7f9fc 100%)}
.app-header{border-bottom:1px solid #ebeef5;padding:16px 24px;background:#fff}
.app-header h1{max-width:1400px;margin:0 auto;color:#303133;font-size:22px}
.topbar{max-width:1400px;margin:0 auto;display:flex;align-items:center;gap:12px;padding:14px 24px}
.panel{max-width:1400px;margin:0 auto;background:#fff;border-radius:12px;padding:18px;box-shadow:0 4px 16px rgba(0,0,0,.06);margin-bottom:24px}
.org-layout{display:flex;min-height:100vh;width:100%}
.org-sidebar{flex:0 0 210px;display:flex;flex-direction:column;background:#fff;border-right:1px solid #eef1f6;padding:20px 12px}
.org-brand{padding:6px 12px 20px;font-size:16px;font-weight:700;color:#2b3a52;letter-spacing:.5px}
.org-menu{display:flex;flex-direction:column;gap:4px}
.org-menu button,.org-bottom button{display:flex;align-items:center;gap:10px;padding:11px 12px;border:0;border-radius:9px;background:transparent;color:#56617a;font-size:14px;cursor:pointer;text-align:left;width:100%}
.org-menu button:hover,.org-bottom button:hover{background:#f3f6fb;color:#2f4f7d}
.org-menu button.active{background:#eaf1fb;color:#3a67a8;font-weight:600}
.ico{font-size:16px;line-height:1}
.org-bottom{margin-top:auto;padding-top:12px;border-top:1px solid #eef1f6}
.org-content{flex:1;min-width:0;padding:24px;background:linear-gradient(180deg,#f0f5ff 0%,#f7f9fc 320px,#f7f9fc 100%);overflow-x:auto}
.org-content :deep(h2.page-title){margin-top:0}
@media(max-width:760px){.org-sidebar{flex-basis:64px;padding:16px 8px}.org-brand{display:none}.org-menu button,.org-bottom button{justify-content:center;padding:11px 0}.org-menu button span:last-child,.org-bottom button span:last-child{display:none}.org-content{padding:14px}}
</style>
