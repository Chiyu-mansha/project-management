<template>
  <div class="notifications-page">
    <div class="toolbar">
      <h2>🔔 通知中心</h2>
      <el-button size="small" @click="load">刷新</el-button>
    </div>

    <el-empty v-if="!loading && list.length === 0" description="暂无通知" />

    <el-timeline v-else v-loading="loading">
      <el-timeline-item
        v-for="item in list"
        :key="item.id"
        :timestamp="item.sent_at"
        :type="item.is_read ? 'info' : 'primary'"
        placement="top"
      >
        <el-card
          :class="{ unread: !item.is_read }"
          shadow="hover"
          @click="handleRead(item)"
        >
          <div class="card-head">
            <el-tag size="small" effect="plain">{{ item.type }}</el-tag>
            <span v-if="!item.is_read" class="unread-dot" />
          </div>
          <div class="card-body">{{ item.content }}</div>
        </el-card>
      </el-timeline-item>
    </el-timeline>

    <div v-if="total > pageSize" class="pager">
      <el-pagination
        layout="prev, pager, next"
        :total="total"
        :page-size="pageSize"
        :current-page="page"
        @current-change="onPageChange"
      />
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { createApiClient } from '../api/request'
import { createNotificationApi } from '../api/notifications'

// MVP 阶段：POD-2 认证域未上线，先返回占位 token（后端目前不校验）。
// 等 POD-2 认证上线后，改成从 localStorage 或 token store 里取真实 token。
const CURRENT_USER_ID = 1
const request = createApiClient({
  getToken: () => 'temp-mock-token',
})
const api = createNotificationApi(request)

const list = ref([])
const total = ref(0)
const page = ref(1)
const pageSize = ref(20)
const loading = ref(false)

async function load() {
  loading.value = true
  try {
    const data = await api.list(CURRENT_USER_ID, page.value, pageSize.value)
    list.value = data.items
    total.value = data.total
  } catch (e) {
    ElMessage.error(e.message || '加载失败')
  } finally {
    loading.value = false
  }
}

async function handleRead(item) {
  if (item.is_read) return
  try {
    const data = await api.markRead(item.id)
    item.is_read = data.is_read
    ElMessage.success('已标记为已读')
  } catch (e) {
    ElMessage.error(e.message || '操作失败')
  }
}

function onPageChange(newPage) {
  page.value = newPage
  load()
}

onMounted(load)
</script>

<style scoped>
.notifications-page { padding: 8px 0; }
.toolbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:16px; }
.toolbar h2 { margin:0; font-size:18px; color:#303133; }
.card-head { display:flex; align-items:center; gap:8px; margin-bottom:8px; }
.unread-dot { width:8px; height:8px; border-radius:50%; background:#f56c6c; display:inline-block; }
.card-body { color:#303133; line-height:1.6; }
.unread { border-left: 3px solid #409eff; }
.pager { text-align:center; margin-top:16px; }
</style>