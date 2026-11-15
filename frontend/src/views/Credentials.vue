<template>
  <div>
    <div class="head">
      <h2 class="page-title">我的凭证</h2>
      <el-button type="primary" plain :loading="exporting" @click="exportMine">导出已签章名单</el-button>
    </div>
    <el-alert v-if="error" :title="error" type="error" show-icon :closable="false" class="mb" />
    <el-radio-group v-model="status" size="small" class="mb" @change="load">
      <el-radio-button label="">全部</el-radio-button>
      <el-radio-button label="issued">已签到</el-radio-button>
      <el-radio-button label="confirmed">已确认</el-radio-button>
      <el-radio-button label="signed">已签章</el-radio-button>
    </el-radio-group>
    <el-table v-loading="loading" :data="items" empty-text="还没有凭证，先去活动详情报名并签到">
      <el-table-column prop="title" label="活动" min-width="180" />
      <el-table-column prop="status" label="状态" width="110">
        <template #default="{ row }">
          <el-tag :type="statusType(row.status)" size="small">{{ statusText(row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column prop="checkin_time" label="签到时间" min-width="160" />
      <el-table-column label="操作" width="140">
        <template #default="{ row }">
          <el-button v-if="row.status === 'signed'" link type="primary" @click="openPdf(row.id)">下载 PDF</el-button>
          <span v-else class="muted">待签章</span>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { onMounted, ref } from 'vue'
import { ElMessage } from 'element-plus'
import { createApiClient } from '../api/request.js'
import { createCredentialApi } from '../api/credentials.js'
import { session } from '../auth/session.js'

const request = createApiClient({ getToken: () => session.value?.token || '' })
const api = createCredentialApi(request)
const items = ref([])
const loading = ref(false)
const exporting = ref(false)
const error = ref('')
const status = ref('')

const statusText = (value) => ({ issued: '已签到', confirmed: '已确认', signed: '已签章' }[value] || value)
const statusType = (value) => ({ issued: 'info', confirmed: 'warning', signed: 'success' }[value] || '')

async function load() {
  loading.value = true
  error.value = ''
  try {
    const data = await api.myCredentials(status.value || undefined)
    items.value = data.items || []
  } catch (e) {
    error.value = e.message || '加载失败'
  } finally {
    loading.value = false
  }
}

async function exportMine() {
  exporting.value = true
  try {
    const data = await api.exportCredentials()
    ElMessage.success(`已生成导出文件，共 ${data.row_count} 条`)
    if (data.download_url) window.open(data.download_url, '_blank')
  } catch (e) {
    ElMessage.error(e.message || '导出失败')
  } finally {
    exporting.value = false
  }
}

function openPdf(id) {
  const token = session.value?.token || ''
  fetch(api.pdfUrl(id), { headers: { Authorization: `Bearer ${token}` } })
    .then((res) => {
      if (!res.ok) throw new Error('下载失败')
      return res.blob()
    })
    .then((blob) => {
      const url = URL.createObjectURL(blob)
      window.open(url, '_blank')
    })
    .catch((e) => ElMessage.error(e.message))
}

onMounted(load)
</script>

<style scoped>
.head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:16px}
.page-title{margin:0}
.mb{margin-bottom:14px}
.muted{color:#98a2b3;font-size:13px}
</style>
