<template>
  <div class="home">
    <div class="badge">POD-1 · member-3</div>
    <h1>校园活动智能助手</h1>
    <p class="sub">请选择要进入的工作台</p>
    <div class="cards">
      <el-card class="pick" shadow="hover" @click="$router.push('/faqs')">
        <div class="emoji">📚</div>
        <h3>FAQ 知识库</h3>
        <el-button type="primary" round>进入管理 →</el-button>
      </el-card>
      <el-card class="pick" shadow="hover" @click="$router.push('/qa')">
        <div class="emoji">💬</div>
        <h3>智能答疑</h3>
        <el-button type="success" round>去提问 →</el-button>
      </el-card>
      <el-card class="pick" shadow="hover" @click="$router.push('/activities')">
        <div class="emoji">📅</div>
        <h3>活动发布</h3>
        <el-button type="warning" round>进入管理 →</el-button>
      </el-card>
    </div>
    <div class="status"><span class="dot" :class="{ok}"></span>{{ msg }}</div>
  </div>
</template>
<script setup>
import { ref, onMounted } from 'vue'
const msg = ref('检测后端中…')
onMounted(async () => { try { const d = await (await fetch('http://localhost:8000/api/hello')).json(); msg.value = '后端已连通 · ' + d.message } catch { msg.value = '后端未启动，请先跑 uvicorn' } })
</script>
<style scoped>
.home{max-width:800px;margin:60px auto;text-align:center}
.badge{display:inline-block;background:#e8efff;color:#3a5bff;font-size:12px;padding:4px 12px;border-radius:20px}
h1{font-size:36px;margin:12px 0 4px}
.sub{color:#666;margin-bottom:28px}
.cards{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.pick{cursor:pointer;padding:10px}
.pick:hover{transform:translateY(-3px)}
.emoji{font-size:48px}
.pick h3{margin:8px 0 4px}
.pick p{color:#666;font-size:14px;min-height:40px}
.status{margin-top:24px;color:#888;font-size:13px}
.dot{display:inline-block;width:9px;height:9px;border-radius:50%;background:#22c55e;margin-right:6px}
</style>
