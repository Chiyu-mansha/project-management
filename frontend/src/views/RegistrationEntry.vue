<script setup>
import { nextTick, ref, watch } from 'vue'
import RegistrationDomain from '../domain/RegistrationDomain.vue'
import { session, clearSession } from '../auth/session.js'
const domain = ref(null)
watch(session, async (value) => {
  await nextTick()
  if (value?.role === 'student') await domain.value?.openMyRegistrations()
}, { immediate: true })
</script>

<template>
  <RegistrationDomain ref="domain" :session="session" @session-expired="clearSession">
    <template #home>
      <el-empty :description="session ? '请从自己发布的活动详情页管理报名表单和名单' : '请先登录，再查看我的报名'">
        <el-button type="primary" @click="$router.push('/activities')">查看活动</el-button>
      </el-empty>
      <el-button v-if="session?.role === 'student'" @click="domain.openMyRegistrations()">查看我的报名</el-button>
    </template>
  </RegistrationDomain>
</template>
