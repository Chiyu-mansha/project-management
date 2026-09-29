<template>
  <div style="padding: 40px">
    <h2>校园活动智能通知&报名助理</h2>
    <p>后端状态:{{ msg }}</p>
    <el-button type="primary" @click="check">检测后端连接</el-button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const msg = ref('未检测')

const check = async () => {
  try {
    const r = await fetch('http://localhost:8000/api/hello')
    const d = await r.json()
    msg.value = '已连通:' + d.message
  } catch (e) {
    msg.value = '连接失败,请确认后端已启动(uvicorn main:app)'
  }
}
</script>
