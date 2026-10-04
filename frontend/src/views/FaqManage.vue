<template>
  <div>
    <div class="toolbar">
      <el-select v-model="query.status" placeholder="状态" clearable style="width:110px" @change="load">
        <el-option label="待审核" value="draft" /><el-option label="已发布" value="published" />
      </el-select>
      <el-select v-model="query.category" placeholder="分类筛选" clearable style="width:160px" @change="load" @keyup.enter="load">
        <el-option v-for="c in CATS" :key="c" :label="c" :value="c" />
      </el-select>
      <el-select v-model="query.activity_id" placeholder="按活动名称筛选" clearable filterable style="width:200px" @change="load" @keyup.enter="load">
        <el-option v-for="a in activities" :key="a.id" :label="a.title" :value="a.id" />
      </el-select>
      <el-input v-model="query.keyword" placeholder="输入关键词搜索" clearable :prefix-icon="Search" style="width:220px" @keyup.enter="load" />
      <el-button type="primary" @click="load">搜索</el-button>
      <el-button type="danger" @click="clearQuery">一键清空</el-button>
      <el-button type="success" @click="openAdd">+ 新增 FAQ</el-button>
      <el-button type="warning" @click="genDlg = true">✨ 推文AI提取</el-button>
      <el-button type="primary" plain @click="openCandidates">🔥 高频待沉淀</el-button>
      <span class="total">共 {{ total }} 条</span>
    </div>

    <el-table :data="rows" border v-loading="loading" :row-class-name="groupClass" style="width:calc(100% + 200px)" :header-cell-style="{background:'#f5f7fa'}">
      <el-table-column prop="category" label="分类" width="140">
        <template #default="s"><el-tag :color="catColor(s.row.category)" effect="dark" round>{{ s.row.category || '未分类' }}</el-tag></template>
      </el-table-column>
      <el-table-column prop="activity_title" label="活动名称" min-width="160">
        <template #default="s"><span class="act">{{ s.row.activity_title || '通用' }}</span></template>
      </el-table-column>
      <el-table-column prop="question" label="问题" min-width="200" />
      <el-table-column prop="answer" label="答案" min-width="220" show-overflow-tooltip />
      <el-table-column prop="source" label="来源" width="130">
        <template #default="s">
          <el-tag :type="s.row.source==='auto'?'warning':'info'">{{ s.row.source }}</el-tag>
          <div v-if="s.row.origin_title" class="origin">← {{ s.row.origin_title }}</div>
        </template>
      </el-table-column>
      <el-table-column prop="status" label="状态" width="90">
        <template #default="s"><el-tag :type="s.row.status==='draft'?'danger':'success'">{{ s.row.status==='draft'?'待审核':'已发布' }}</el-tag></template>
      </el-table-column>
      <el-table-column label="操作" width="170">
        <template #default="s">
          <div class="ops">
          <el-button v-if="s.row.status==='draft'" size="small" type="success" link @click="approve(s.row)">审核发布</el-button>
          <el-button size="small" link type="primary" @click="openEdit(s.row)">修改</el-button>
          <el-button size="small" link type="danger" @click="removeRow(s.row)">删除</el-button>
          </div>
        </template>
      </el-table-column>
    </el-table>

    <el-dialog v-model="dlg" :title="form.id?'编辑 FAQ':'新增 FAQ'" width="520px">
      <el-form :model="form" label-width="70px">
        <el-form-item label="分类">
          <el-select v-model="form.category" style="width:100%">
            <el-option v-for="c in CATS" :key="c" :label="c" :value="c" />
          </el-select>
        </el-form-item>
        <el-form-item label="活动"><el-select v-model="form.activity_id" placeholder="输入名称检索，不存在直接回车新建" clearable filterable allow-create default-first-option style="width:100%"><el-option v-for="a in activities" :key="a.id" :label="a.title" :value="a.id" /></el-select></el-form-item>
        <el-form-item label="问题"><el-input v-model="form.question" type="textarea" :rows="2" /></el-form-item>
        <el-form-item label="答案"><el-input v-model="form.answer" type="textarea" :rows="3" /></el-form-item>
        <el-form-item label="状态"><el-radio-group v-model="form.status"><el-radio-button label="published">已发布</el-radio-button><el-radio-button label="draft">草稿</el-radio-button></el-radio-group></el-form-item>
      </el-form>
      <template #footer><el-button @click="dlg=false">取消</el-button><el-button type="primary" @click="save">保存</el-button></template>
    </el-dialog>

    <el-dialog v-model="genDlg" title="✨ 推文 AI 提取 FAQ" width="560px">
      <p style="color:#888;margin-top:0">推文发布后粘贴到这里，AI 自动提取 3-5 个常见问答，以 <b>待审核(draft)</b> 存入，管理员修改后发布。</p>
      <el-form :model="genForm" label-width="70px">
        <el-form-item label="推文标题"><el-input v-model="genForm.title" placeholder="如：编程马拉松报名启动" /></el-form-item>
        <el-form-item label="活动"><el-select v-model="genForm.activity_id" placeholder="选择活动" clearable filterable style="width:100%"><el-option v-for="a in activities" :key="a.id" :label="a.title" :value="a.id" /></el-select></el-form-item>
        <el-form-item label="分类"><el-select v-model="genForm.category" style="width:100%"><el-option v-for="c in CATS" :key="c" :label="c" :value="c" /></el-select></el-form-item>
        <el-form-item label="推文内容"><el-input v-model="genForm.content" type="textarea" :rows="6" placeholder="粘贴推文正文…" /></el-form-item>
      </el-form>
      <template #footer><el-button @click="genDlg=false">取消</el-button><el-button type="warning" :loading="genLoading" @click="autoGen">AI 提取</el-button></template>
    </el-dialog>

    <el-dialog v-model="candDlg" title="🔥 高频提问待沉淀" width="720px">
      <p style="color:#888;margin-top:0">系统记录了用户答疑，这里列出被反复问到、但知识库还没有的问题，审核后沉淀为 FAQ 草稿。</p>
      <div style="margin-bottom:10px">
        <span style="color:#666;font-size:13px">最低出现次数：</span>
        <el-input-number v-model="candMin" :min="1" :max="99" size="small" @change="loadCandidates" />
        <el-button size="small" style="margin-left:8px" :loading="candLoading" @click="loadCandidates">刷新</el-button>
      </div>
      <el-table :data="candidates" border size="small" v-loading="candLoading" empty-text="暂无达到阈值的候选，多问几次同样的未命中问题就会出现">
        <el-table-column prop="question" label="问题" min-width="220" />
        <el-table-column prop="count" label="出现次数" width="90">
          <template #default="s"><el-tag type="danger" size="small">{{ s.row.count }} 次</el-tag></template>
        </el-table-column>
        <el-table-column prop="answer" label="AI 原答案" min-width="220" show-overflow-tooltip />
        <el-table-column label="操作" width="90">
          <template #default="s"><el-button size="small" type="success" link @click="acceptCandidate(s.row)">沉淀</el-button></template>
        </el-table-column>
      </el-table>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { Search } from '@element-plus/icons-vue'
const API = 'http://localhost:8000'
const CATS = ['竞赛类', '讲座/分享类', '培训/工作坊类', '招募类', '文体活动类', '通知类']
const CAT_COLORS = { '竞赛类': '#6366f1', '讲座/分享类': '#0ea5e9', '培训/工作坊类': '#8b5cf6', '招募类': '#f59e0b', '文体活动类': '#22c55e', '通知类': '#64748b' }
const catColor = (c) => CAT_COLORS[c] || '#909399'
const rows = ref([]); const total = ref(0); const loading = ref(false)
const activities = ref([])
const query = reactive({ keyword: '', activity_id: '', category: '', status: '' })
const dlg = ref(false)
const form = reactive({ id: null, question: '', answer: '', activity_id: null, category: '通知类', status: 'published', source: 'manual' })

// 按活动+分类分组：activity_id 相同且 category 相同的连续行同一组
// 活动表为空时 activity_id 全是 null，就退化为按 category 分组，保证颜色能交替
let groupMap = {}
const groupKey = (r) => `${r.activity_id ?? 'null'}__${r.category || ''}`
const buildGroups = (list) => {
  groupMap = {}
  let g = 0, prev = null
  list.forEach((r) => {
    const k = groupKey(r)
    if (k !== prev) { g++; prev = k }
    groupMap[r.id] = g
  })
}
const groupClass = ({ row }) => (groupMap[row.id] % 2 === 0 ? 'grp-a' : 'grp-b')

const loadActivities = async () => { try { const d = await (await fetch(`${API}/api/activities`)).json(); activities.value = d.items || [] } catch { activities.value = [] } }
const load = async () => {
  loading.value = true
  try {
    const p = new URLSearchParams({ page: 1, page_size: 100 })
    if (query.keyword) p.append('keyword', query.keyword)
    if (query.category) p.append('category', query.category)
    if (query.status) p.append('status', query.status)
    if (query.activity_id !== '' && query.activity_id !== null) p.append('activity_id', query.activity_id)
    const d = await (await fetch(`${API}/api/faqs?${p}`)).json()
    const list = (d.items || []).sort((a, b) => (a.activity_id ?? -1) - (b.activity_id ?? -1) || String(a.category).localeCompare(String(b.category)))
    buildGroups(list)
    rows.value = list; total.value = d.total
  } finally { loading.value = false }
}
const openAdd = () => { Object.assign(form, { id: null, question: '', answer: '', activity_id: null, category: '通知类', status: 'published', source: 'manual' }); dlg.value = true }
const openEdit = (r) => { Object.assign(form, { ...r }); dlg.value = true }
const clearQuery = () => { query.keyword = ''; query.activity_id = ''; query.category = ''; query.status = ''; load() }
const genDlg = ref(false)
const genForm = reactive({ title: '', content: '', activity_id: null, category: '通知类' })
const genLoading = ref(false)
const autoGen = async () => {
  if (!genForm.content.trim()) return ElMessage.warning('先粘贴推文内容')
  genLoading.value = true
  try {
    const d = await (await fetch(`${API}/api/faqs/auto-generate`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(genForm) })).json()
    ElMessage.success(`AI提取${d.total}条，已存为待审核`)
    genDlg.value = false; query.status = 'draft'; load()
  } finally { genLoading.value = false }
}
const approve = async (r) => {
  await fetch(`${API}/api/faqs/${r.id}`, { method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ ...r, status: 'published' }) })
  ElMessage.success('已发布'); load()
}
const candDlg = ref(false); const candidates = ref([]); const candLoading = ref(false); const candMin = ref(3)
const openCandidates = () => { candDlg.value = true; loadCandidates() }
const loadCandidates = async () => {
  candLoading.value = true
  try { const d = await (await fetch(`${API}/api/qa/candidates?min_count=${candMin.value}`)).json(); candidates.value = d.items || [] } finally { candLoading.value = false }
}
const acceptCandidate = async (r) => {
  await fetch(`${API}/api/qa/candidates/accept`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: r.question, answer: r.answer, activity_id: r.activity_id }) })
  ElMessage.success('已沉淀为待审核 FAQ'); candidates.value = candidates.value.filter(x => x.question !== r.question)
}
const save = async () => {
  const body = { ...form }; const id = body.id; delete body.id
  if (!body.question.trim() || !body.answer.trim()) return ElMessage.error('问题和答案不能为空')
  // 直接输入了新活动名称（字符串）→ 先建活动再拿 id
  if (typeof body.activity_id === 'string' && body.activity_id.trim() !== '') {
    const r = await fetch(`${API}/api/activities`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ title: body.activity_id.trim() }) })
    const created = await r.json()
    body.activity_id = created.id
    activities.value.unshift(created)
  }
  if (body.activity_id === '') body.activity_id = null
  const r = await fetch(id ? `${API}/api/faqs/${id}` : `${API}/api/faqs`, { method: id ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) })
  if (!r.ok) return ElMessage.error('保存失败')
  ElMessage.success('保存成功'); dlg.value = false; load()
}
const removeRow = async (r) => { await fetch(`${API}/api/faqs/${r.id}`, { method: 'DELETE' }); ElMessage.success('已删除'); load() }
onMounted(() => { loadActivities(); load() })
</script>

<style scoped>
.toolbar{display:flex;gap:10px;align-items:center;margin-bottom:12px;flex-wrap:wrap}
.total{margin-left:auto;color:#888;font-size:13px}
.act{font-weight:600}
.ops{white-space:nowrap}
.ops .el-button{margin-left:4px;padding:2px 4px}
.origin{font-size:11px;color:#999;margin-top:2px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:120px}
.legend{margin-top:8px;color:#999;font-size:12px}
</style>
<style>
.el-table .grp-a > td{background-color:#eef4ff !important;border-bottom:2px solid #b6c8ff !important}
.el-table .grp-b > td{background-color:#fff8e6 !important;border-bottom:2px solid #f0d48a !important}
.el-table .grp-a:hover > td{background-color:#e0ebff !important}
.el-table .grp-b:hover > td{background-color:#ffefc4 !important}
</style>
