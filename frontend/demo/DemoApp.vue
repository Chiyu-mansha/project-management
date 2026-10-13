<script setup>
import { computed, ref } from 'vue'
import RegistrationDomain from '../src/domain/RegistrationDomain.vue'

// 演示身份切换：发布者 / 学生·张三 / 学生·李四（token 对应后端临时鉴权 role:id）
const role = ref('organizer')
const session = computed(() => {
  if (role.value === 'organizer') return { token: 'organizer:1', role: 'organizer', id: 1 }
  if (role.value === 'student2') return { token: 'student:2', role: 'student', id: 2 }
  return { token: 'student:1', role: 'student', id: 1 }
})

// 临时 field_key 生成规则（文档未定稿，先按序号占位，保证能新增题目）
let keySeq = 0
const generateFieldKey = () => `field_${++keySeq}`

// 报名详情响应 → 弹窗内部格式 的适配（对应文档 GET /api/registrations/{id} 的返回）
const readRegistrationDetail = (data) => ({
  teamSchema: data.form.form_team_schema,
  memberSchema: data.form.form_member_schema,
  teamExtra: data.extra_fields.team_extra,
  members: data.extra_fields.members,
  isIndividual: data.form.min_team_member === 1 && data.form.max_team_member === 1
})
</script>

<template>
  <main>
    <header class="app-header">
      <h1>校园活动智能通知&amp;报名助理（演示）</h1>
      <div class="role-switch">
        <el-button :type="role === 'organizer' ? 'primary' : ''" @click="role = 'organizer'">发布者</el-button>
        <el-button :type="role === 'student1' ? 'primary' : ''" @click="role = 'student1'">学生·张三</el-button>
        <el-button :type="role === 'student2' ? 'primary' : ''" @click="role = 'student2'">学生·李四</el-button>
      </div>
    </header>

    <RegistrationDomain ref="domain" :session="session" :generate-field-key="generateFieldKey" :read-registration-detail="readRegistrationDetail">
      <template #home="actions">
        <div class="demo-buttons">
          <template v-if="role === 'organizer'">
            <el-button type="primary" @click="actions.openCreateForm(1)">创建表单(活动1·组队)</el-button>
            <el-button @click="actions.openFormTemplate(1)">查看/编辑表单(活动1)</el-button>
            <el-button @click="actions.openActivityRegistrations(1)">获取报名信息(活动1)</el-button>
            <el-button type="primary" @click="actions.openCreateForm(2)">创建表单(活动2·单人)</el-button>
          </template>
          <template v-else>
            <el-button type="primary" @click="actions.openRegistration(1)">报名(活动1·组队)</el-button>
            <el-button @click="actions.openRegistration(2)">报名(活动2·单人)</el-button>
            <el-button @click="actions.openMyRegistrations()">我的报名</el-button>
          </template>
        </div>
      </template>
    </RegistrationDomain>
  </main>
</template>

<style>
body { margin: 0; font-family: system-ui, "Microsoft YaHei", sans-serif; background: #fff; }
.app-header { border-bottom: 1px solid #ebeef5; padding: 16px 24px; display: flex; align-items: center; gap: 24px; flex-wrap: wrap; }
.app-header h1 { margin: 0; color: #303133; font-size: 20px; }
.role-switch { display: flex; gap: 8px; }
.demo-buttons { padding: 24px; display: flex; flex-wrap: wrap; gap: 12px; }
</style>
