<template>
  <div class="page">
    <nav v-if="$route.path !== '/'" class="topbar">
      <el-button link @click="$router.push('/')">↩ 返回</el-button>
      <span v-if="$route.path === '/faqs'" class="title">📚 FAQ 知识库</span>
    </nav>
    <main :class="{panel: $route.path !== '/'}"><router-view /></main>
  </div>
</template>
<style scoped>
.page{min-height:100vh;background:linear-gradient(180deg,#f0f5ff 0%,#f7f9fc 320px,#f7f9fc 100%);padding:20px}
.topbar{max-width:1400px;margin:0 auto 14px;display:flex;align-items:center;gap:12px}
.title{font-weight:700;font-size:18px}
.panel{max-width:1400px;margin:0 auto;background:#fff;border-radius:12px;padding:18px;box-shadow:0 4px 16px rgba(0,0,0,.06)}
</style>
