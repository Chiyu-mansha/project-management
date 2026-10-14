<template>
  <div>
    <div class="toolbar">
      <el-select v-model="query.type" placeholder="活动类型" clearable filterable allow-create default-first-option style="width:150px" @change="load">
        <el-option v-for="t in TYPES" :key="t" :label="t" :value="t" />
      </el-select>
      <el-select v-model="query.status" placeholder="状态" clearable style="width:120px" @change="load">
        <el-option label="草稿" value="draft" /><el-option label="已发布" value="published" />
        <el-option label="进行中" value="ongoing" /><el-option label="已结束" value="finished" />
        <el-option label="已取消" value="cancelled" />
      </el-select>
      <el-input v-model="query.tags" placeholder="标签筛选" clearable style="width:160px" @keyup.enter="load" />
      <el-input v-model="query.keyword" placeholder="搜索标题/简介" clearable :prefix-icon="Search" style="width:220px" @keyup.enter="load" />
      <el-button type="primary" @click="load">搜索</el-button>
      <el-button type="success" @click="$router.push('/activities/new')">+ 发布活动</el-button>
      <span class="total">共 {{ total }} 条</span>
    </div>

    <el-table :data="rows" border v-loading="loading" :header-cell-style="{background:'#f5f7fa'}" @row-click="(r) => $router.push(`/activities/${r.id}`)" style="cursor:pointer">
      <el-table-column prop="title" label="活动名称" min-width="170">
        <template #default="s"><span class="act">{{ s.row.title }}</span></template>
      </el-table-column>
      <el-table-column prop="type" label="类型" width="120">
        <template #default="s"><el-tag v-if="s.row.type" type="primary" effect="plain">{{ s.row.type }}</el-tag></template>
      </el-table-column>
      <el-table-column label="开始时间" width="160">
        <template #default="s">{{ fmtTime(s.row.start_time) }}</template>
      </el-table-column>
      <el-table-column prop="location" label="地点" min-width="120" />
      <el-table-column prop="status" label="状态" width="90">
        <template #default="s">
          <el-tag :type="statusType(s.row.status)">{{ statusText(s.row.status) }}</el-tag>
        </template>
      </el-table-column>
      <el-table-column label="操作" width="140">
        <template #default="s">
          <el-button size="small" link type="primary" @click.stop="$router.push(`/activities/${s.row.id}`)">查看</el-button>
          <el-button size="small" link type="warning" @click.stop="$router.push(`/activities/${s.row.id}/edit`)">编辑</el-button>
        </template>
      </el-table-column>
    </el-table>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { Search } from '@element-plus/icons-vue'

const API = 'http://localhost:8000'
const TYPES = ['学科类', '文体类', '科创竞赛', '社会实践']
const rows = ref([])
const total = ref(0)
const loading = ref(false)
const query = reactive({ type: '', tags: '', keyword: '', status: '' })

const fmtTime = (s) => (s ? String(s).replace('T', ' ') : '—')
const STATUS = {
  draft: { text: '草稿', type: 'info' },
  published: { text: '已发布', type: 'success' },
  ongoing: { text: '进行中', type: 'warning' },
  finished: { text: '已结束', type: 'primary' },
  cancelled: { text: '已取消', type: 'danger' },
}
const statusText = (s) => STATUS[s]?.text || s
const statusType = (s) => STATUS[s]?.type || 'info'

const load = async () => {
  loading.value = true
  try {
    const p = new URLSearchParams({ page: 1, page_size: 100 })
    if (query.type) p.append('type', query.type)
    if (query.tags) p.append('tags', query.tags)
    if (query.keyword) p.append('keyword', query.keyword)
    if (query.status) p.append('status', query.status)
    const d = await (await fetch(`${API}/api/activities?${p}`)).json()
    rows.value = d.data?.items || []
    total.value = d.data?.total || 0
  } finally {
    loading.value = false
  }
}

onMounted(load)
</script>

<style scoped>
.toolbar{display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
.total{margin-left:auto;color:#888;font-size:13px}
.act{font-weight:600}
</style>
