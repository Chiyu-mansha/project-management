<script setup>
// 报名管理入口(PM 合并仪式 10-14):POD-2 在 d2c18b1 清理了 frontend/demo 演示代码(原则:不虚构会话),
// 此处按 INTEGRATION.md 的正式挂载方式裸挂报名域。session 由 POD-2 本周交付的登录域接入。
import RegistrationDomain from '../domain/RegistrationDomain.vue'
</script>

<template>
  <RegistrationDomain />
</template>
