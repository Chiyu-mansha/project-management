<template>
  <div>
    <div class="head">
      <h2 class="page-title">签到核销</h2>
      <el-button @click="$router.push(`/activities/${activityId}`)">返回活动</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="mb" />
    <div class="actions mb">
      <el-button type="primary" :disabled="!selected.length" @click="confirmSelected">确认选中名单</el-button>
      <el-button type="success" :disabled="!canSign.length" @click="signConfirmed">为已确认项签章</el-button>
    </div>
    <el-table v-loading="loading" :data="items" @selection-change="selected = $event">
      <el-table-column type="selection" width="46" :selectable="(row) => row.status === 'issued'" />
      <el-table-column prop="student_id" label="学号" width="140" />
      <el-table-column prop="student_name" label="姓名" width="120" />
      <el-table-column prop="status" label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="checkin_time" label="签到时间" min-width="180" />
    </el-table>
  </div>
</template>

<script setup>
import { computed, onMounted, ref } from 'vue'
import { useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import { createApiClient } from '../api/request.js'
import { createCredentialApi } from '../api/credentials.js'
import { session } from '../auth/session.js'

const route = useRoute()
const activityId = route.params.id
const request = createApiClient({ getToken: () => session.value?.token || '' })
const api = createCredentialApi(request)
const items = ref([])
const selected = ref([])
const loading = ref(false)
const error = ref('')

const canSign = computed(() => items.value.filter((row) => row.status === 'confirmed'))
const statusText = (value) => ({ issued: '已签到', confirmed: '已确认', signed: '已签章' }[value] || value)
const statusType = (value) => ({ issued: 'info', confirmed: 'warning', signed: 'success' }[value] || '')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.checkinList(activityId)
    items.value = data.items || []
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function confirmSelected() {
  try {
    await api.confirm(activityId, selected.value.map((row) => row.id))
    ElMessage.success('名单已确认')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '确认失败')
  }
}

async function signConfirmed() {
  try {
    for (const row of canSign.value) {
      await api.sign(row.id)
    }
    ElMessage.success('签章完成')
    await load()
  } catch (e) {
    ElMessage.error(e.message || '签章失败')
  }
}

onMounted(load)
</script>

<style scoped>
.head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px}
.page-title{margin:0}
.mb{margin-bottom:14px}
.actions{display:flex;gap:8px}
</style>
