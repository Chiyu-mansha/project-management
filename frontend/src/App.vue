<script setup>
</script>

<template>
  <div class="page">
    <header class="app-header"><h1>校园活动智能通知&amp;报名助理</h1></header>
    <nav class="topbar">
      <el-button link @click="$router.push('/')">🏠 首页</el-button>
      <el-button link @click="$router.push('/faqs')">📚 FAQ 知识库</el-button>
      <el-button link @click="$router.push('/qa')">💬 智能答疑</el-button>
      <el-button link @click="$router.push('/activities')">📅 活动发布</el-button>
      <el-button link @click="$router.push('/registrations')">📝 报名管理(演示)</el-button>
    </nav>
    <main :class="{panel: $route.path !== '/'}"><router-view /></main>
  </div>
</template>

<style scoped>
.page{min-height:100vh;background:linear-gradient(180deg,#f0f5ff 0%,#f7f9fc 320px,#f7f9fc 100%)}
.app-header{border-bottom:1px solid #ebeef5;padding:16px 24px;background:#fff}
.app-header h1{max-width:1400px;margin:0 auto;color:#303133;font-size:22px}
.topbar{max-width:1400px;margin:0 auto;display:flex;align-items:center;gap:12px;padding:14px 24px}
.panel{max-width:1400px;margin:0 auto;background:#fff;border-radius:12px;padding:18px;box-shadow:0 4px 16px rgba(0,0,0,.06);margin-bottom:24px}
</style>
