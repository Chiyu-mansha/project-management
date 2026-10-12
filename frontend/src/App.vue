<script setup>
import RegistrationDomain from './domain/RegistrationDomain.vue'
</script>

<template>
  <main>
    <header class="app-header"><h1>校园活动智能通知&amp;报名助理</h1></header>
    <RegistrationDomain />
  </main>
</template>

<style>
body { margin: 0; font-family: system-ui, "Microsoft YaHei", sans-serif; background: #fff; }
.app-header { border-bottom: 1px solid #ebeef5; padding: 20px 24px; }
.app-header h1 { max-width: 1080px; margin: 0 auto; color: #303133; font-size: 22px; }
</style>
