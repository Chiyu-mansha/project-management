<template>
  <div class="qa-layout">
    <aside class="sidebar">
      <div class="brand"><span class="brand-emoji">💬</span><span>智能答疑</span></div>
      <el-button class="new-chat" type="primary" @click="newChat"><el-icon><Plus /></el-icon>新对话</el-button>

      <div class="side-tool">
        <el-icon><FolderOpened /></el-icon>
        <span>对话分组</span>
        <span class="tool-actions">
          <el-icon class="add-group" title="新建分组" @click.stop="openGroupDlg"><Plus /></el-icon>
          <el-icon class="chevron" :class="{open:showGroups}" @click.stop="showGroups = !showGroups"><ArrowDown /></el-icon>
        </span>
      </div>
      <div v-if="showGroups" class="groups">
        <div v-for="g in groups" :key="g.id" class="group-item" :class="{active:filterGroupId===g.id}" @click="filterGroupId = filterGroupId===g.id ? null : g.id">
          <span class="group-name">{{ g.name }}</span>
          <span class="group-count">{{ g.ids.length }}</span>
          <el-icon class="group-del" @click.stop="removeGroup(g)"><Close /></el-icon>
        </div>
        <div v-if="!groups.length" class="group-empty">还没有分组，点 + 新建</div>
      </div>

      <div class="history-title"><el-icon><Clock /></el-icon>历史记录</div>
      <div class="history-list">
        <template v-for="g in visibleGroups" :key="'g' + g.id">
          <div class="history-group-label">{{ g.name }}</div>
          <div v-for="item in g.items" :key="item.id" class="history-item" :class="{active:item.id === currentId}" @click="selectHistory(item)">
            <span class="history-dot"></span><span class="history-name">{{ item.title }}</span>
          </div>
        </template>
        <div v-for="item in visibleUngrouped" :key="item.id" class="history-item" :class="{active:item.id === currentId}" @click="selectHistory(item)">
          <span class="history-dot"></span><span class="history-name">{{ item.title }}</span>
        </div>
        <div v-if="!history.length" class="empty-history">暂无历史对话</div>
      </div>
      <div class="sidebar-foot">FAQ 知识库 · 智能答疑</div>
    </aside>

    <main class="qa-main">
      <header class="qa-head">
        <el-input v-model="conversationName" class="conversation-name" placeholder="对话名称" />
        <el-select v-model="qa.activity_id" placeholder="选择活动（可选）" clearable filterable class="activity-select">
          <el-option v-for="a in activities" :key="a.id" :label="a.title" :value="a.id" />
        </el-select>
      </header>

      <section class="conversation" ref="conversationRef">
        <el-empty v-if="!messages.length" description="还没有提问，输入你的第一个问题吧" />
        <div v-for="(message, i) in messages" :key="i" class="message-block">
          <div class="msg-row user">
            <div class="bubble user-bubble">{{ message.question }}</div>
            <el-avatar class="avatar user-avatar" :size="36">我</el-avatar>
          </div>
          <div class="msg-row ai">
            <el-avatar class="avatar ai-avatar" :size="36">AI</el-avatar>
            <el-card class="answer-card" shadow="never">
              <div class="ans-head"><span class="answer-label">智能助手</span><el-tag :type="message.source==='faq'?'success':'warning'">{{ message.source==='faq'?'命中知识库':'AI 生成' }}</el-tag><span v-if="message.faq_id" class="fid">faq_id={{ message.faq_id }}</span></div>
              <div class="ans-body">{{ message.answer }}</div>
              <div class="tools">
                <el-tooltip content="复制" placement="top"><el-icon class="tool" @click="copyAnswer(message)"><CopyDocument /></el-icon></el-tooltip>
                <el-tooltip content="赞" placement="top"><span class="tool emoji" :class="{on:message.feedback==='like'}" @click="like(message)">👍</span></el-tooltip>
                <el-tooltip content="踩" placement="top"><span class="tool emoji" :class="{on:message.feedback==='dislike'}" @click="dislike(message)">👎</span></el-tooltip>
                <el-tooltip content="重新生成" placement="top"><el-icon class="tool" @click="regenerate(message)"><Refresh /></el-icon></el-tooltip>
              </div>
            </el-card>
          </div>
        </div>
      </section>

      <section class="composer">
        <el-input v-model="qa.question" type="textarea" :rows="3" resize="none" placeholder="输入问题，按 Ctrl + Enter 发送…" @keydown.ctrl.enter.prevent="ask" />
        <div class="composer-footer"><span class="hint">答案将优先来自 FAQ 知识库</span><el-button type="primary" round @click="ask" :loading="loading">发送问题 ↗</el-button></div>
      </section>
    </main>

    <el-dialog v-model="groupDlg" title="新建对话分组" width="480px">
      <el-form label-width="80px">
        <el-form-item label="分组名称">
          <el-input v-model="groupForm.name" placeholder="如：编程马拉松答疑" />
        </el-form-item>
        <el-form-item label="选择对话">
          <div class="pick-list">
            <el-checkbox-group v-model="groupForm.ids">
              <el-checkbox v-for="h in history" :key="h.id" :label="h.id" class="pick-item">{{ h.title }}</el-checkbox>
            </el-checkbox-group>
            <div v-if="!history.length" class="group-empty">还没有历史对话，先聊几句再来分组</div>
          </div>
        </el-form-item>
      </el-form>
      <template #footer><el-button @click="groupDlg=false">取消</el-button><el-button type="primary" @click="saveGroup">确定</el-button></template>
    </el-dialog>
  </div>
</template>

<script setup>
import { reactive, ref, watch, computed, onMounted, nextTick } from 'vue'
import { ElMessage } from 'element-plus'
import { Plus, FolderOpened, ArrowDown, Clock, Close, CopyDocument, Refresh } from '@element-plus/icons-vue'
const API = 'http://localhost:8000'
const qa = reactive({ question: '', activity_id: '' })
const activities = ref([]); const messages = ref([]); const loading = ref(false); const conversationRef = ref(null)
const history = ref([]); const currentId = ref(1); const showGroups = ref(false); const conversationName = ref('新对话')

const groups = ref([]); const filterGroupId = ref(null)
const groupDlg = ref(false)
const groupForm = reactive({ name: '', ids: [] })
const openGroupDlg = () => { groupForm.name = ''; groupForm.ids = []; groupDlg.value = true }
const saveGroup = () => {
  if (!groupForm.name.trim()) return ElMessage.warning('请输入分组名称')
  if (!groupForm.ids.length) return ElMessage.warning('请至少选择一个对话')
  const exist = groups.value.find(g => g.name === groupForm.name.trim())
  if (exist) { exist.ids = [...new Set([...exist.ids, ...groupForm.ids])] }
  else groups.value.push({ id: Date.now(), name: groupForm.name.trim(), ids: [...groupForm.ids] })
  groupDlg.value = false; showGroups.value = true; ElMessage.success('分组已保存')
}
const removeGroup = (g) => { groups.value = groups.value.filter(x => x.id !== g.id); if (filterGroupId.value === g.id) filterGroupId.value = null }

const groupIdOf = (hid) => groups.value.find(g => g.ids.includes(hid))?.id
const visibleGroups = computed(() => {
  const list = filterGroupId.value ? groups.value.filter(g => g.id === filterGroupId.value) : groups.value
  return list.map(g => ({ ...g, items: history.value.filter(h => g.ids.includes(h.id)) })).filter(g => g.items.length)
})
const visibleUngrouped = computed(() => {
  if (filterGroupId.value) return []
  return history.value.filter(h => !groupIdOf(h.id))
})

const syncHistory = () => { const cur = history.value.find(i => i.id === currentId.value); if (cur) cur.title = conversationName.value }
watch(conversationName, syncHistory)
watch(() => qa.activity_id, (id) => { const a = activities.value.find(x => x.id === id); if (a) conversationName.value = a.title })

const STORAGE_KEY = 'qa_state_v1'
const persist = () => {
  try { localStorage.setItem(STORAGE_KEY, JSON.stringify({ history: history.value, groups: groups.value, currentId: currentId.value, conversationName: conversationName.value, showGroups: showGroups.value })) } catch {}
}
watch([history, groups, currentId, conversationName], persist, { deep: true })
const restore = () => {
  try {
    const s = JSON.parse(localStorage.getItem(STORAGE_KEY) || 'null')
    if (!s) return
    history.value = s.history || []
    groups.value = s.groups || []
    currentId.value = s.currentId || 1
    conversationName.value = s.conversationName || '新对话'
    showGroups.value = s.showGroups || false
    const cur = history.value.find(i => i.id === currentId.value)
    messages.value = cur?.messages || []
    qa.activity_id = cur?.activity_id ?? ''
  } catch {}
}

onMounted(async () => {
  restore()
  try { const d = await (await fetch(`${API}/api/activities`)).json(); activities.value = d.items || [] } catch { activities.value = [] }
})
const newChat = () => { currentId.value = Date.now(); messages.value = []; qa.question = ''; qa.activity_id = ''; conversationName.value = '新对话'; history.value.unshift({ id: currentId.value, title: '新对话', messages: [] }) }
const selectHistory = (item) => { currentId.value = item.id; messages.value = item.messages || []; conversationName.value = item.title; qa.activity_id = item.activity_id ?? '' }
const ask = async () => {
  if (!qa.question.trim()) return ElMessage.warning('先输入问题')
  const question = qa.question.trim(); loading.value = true
  try {
    const answer = await fetchAsk(question, false)
    messages.value.push({ question, ...answer, feedback: null })
    let current = history.value.find(item => item.id === currentId.value)
    if (!current) { current = { id: currentId.value, title: conversationName.value, messages: messages.value }; history.value.unshift(current) }
    current.messages = messages.value; current.activity_id = qa.activity_id
    if (current.title === '新对话' && !qa.activity_id) conversationName.value = question.slice(0, 18)
    qa.question = ''; await nextTick(); scrollToEnd()
  } finally { loading.value = false }
}
const fetchAsk = async (question, noCache) => (await fetch(`${API}/api/qa/ask`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question, activity_id: qa.activity_id === '' ? null : Number(qa.activity_id), no_cache: noCache }) })).json()
const scrollToEnd = () => conversationRef.value?.scrollTo({ top: conversationRef.value.scrollHeight, behavior: 'smooth' })
const copyAnswer = async (message) => {
  try { await navigator.clipboard.writeText(message.answer); ElMessage.success('已复制') } catch { ElMessage.warning('复制失败，请手动选择') }
}
const like = async (message) => {
  message.feedback = message.feedback === 'like' ? null : 'like'
  if (message.feedback === 'like') { await fetch(`${API}/api/qa/feedback`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'like', faq_id: message.faq_id, question: message.question }) }); ElMessage.success('感谢反馈') }
}
const dislike = async (message) => {
  message.feedback = 'dislike'
  const r = await fetch(`${API}/api/qa/feedback`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ action: 'dislike', faq_id: message.faq_id, question: message.question }) })
  const d = await r.json()
  ElMessage.warning(d.faq_downgraded ? '已反馈，该条知识库答案已转为待审核' : '已反馈，我们会尽快优化')
}
const regenerate = async (message) => {
  ElMessage.info('重新生成中…')
  const answer = await fetchAsk(message.question, true)
  Object.assign(message, answer, { feedback: null })
  await nextTick(); scrollToEnd()
}
</script>

<style scoped>
.qa-layout{height:calc(100vh - 96px);min-height:620px;display:flex;overflow:hidden;background:linear-gradient(180deg,#f7f9ff,#fff);margin:-18px}
.sidebar{width:220px;flex:0 0 220px;border-right:1px solid #e5eaf4;background:#f8faff;padding:22px 14px;display:flex;flex-direction:column;box-sizing:border-box}
.brand{display:flex;align-items:center;gap:8px;font-weight:700;font-size:18px;color:#26334d;margin:2px 8px 22px}.brand-emoji{font-size:18px}
.new-chat{width:100%;height:38px;margin-bottom:12px}.new-chat .el-icon{margin-right:6px}
.side-tool{height:38px;display:flex;align-items:center;gap:9px;padding:0 10px;color:#59657a;font-size:13px}
.side-tool .tool-actions{margin-left:auto;display:flex;align-items:center;gap:6px}
.side-tool .add-group,.side-tool .chevron{font-size:14px;padding:2px;border-radius:4px;cursor:pointer}
.side-tool .add-group:hover{background:#dfe8ff;color:#3a5bff}
.side-tool .chevron{transition:transform .2s}.side-tool .chevron.open{transform:rotate(180deg)}
.groups{padding:2px 0 8px 4px}.group-item{display:flex;align-items:center;gap:6px;padding:7px 9px;color:#8791a3;font-size:12px;border-radius:6px;cursor:pointer}.group-item:hover{background:#eef3ff}.group-item.active{color:#3a5bff;background:#e8efff}.group-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.group-count{margin-left:auto;background:#e3e9f7;color:#7b8699;border-radius:9px;padding:0 6px;font-size:11px}.group-del{opacity:0;font-size:12px}.group-item:hover .group-del{opacity:1;color:#f56c6c}.group-empty{padding:8px 10px 4px;color:#aab2c0;font-size:12px}
.history-title{height:38px;display:flex;align-items:center;gap:9px;padding:0 10px;margin-top:6px;color:#8b95a7;font-size:12px}
.history-list{overflow-y:auto}
.history-group-label{padding:8px 10px 4px;color:#9aa4b5;font-size:11px;font-weight:600;letter-spacing:.5px}
.history-item{display:flex;align-items:center;gap:8px;padding:10px;border-radius:8px;color:#536078;font-size:13px;cursor:pointer;margin:2px 0}.history-item:hover,.history-item.active{background:#e8efff;color:#3a5bff}
.history-dot{width:7px;height:7px;border:2px solid #a9b8d5;border-radius:50%;flex:none}.history-item.active .history-dot{border-color:#3a5bff;background:#3a5bff}
.history-name{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.empty-history{padding:12px 10px;color:#aab2c0;font-size:12px}
.sidebar-foot{margin-top:auto;color:#a2acbc;font-size:11px;padding:12px 8px;border-top:1px solid #e5eaf4}
.qa-main{flex:1;min-width:0;display:flex;flex-direction:column;padding:28px 46px 30px}.qa-head{display:flex;align-items:center;justify-content:space-between;border-bottom:1px solid #e8edf7;padding:4px 0 18px;gap:20px}.conversation-name{max-width:520px}.conversation-name :deep(.el-input__wrapper){box-shadow:none;background:transparent;padding:0}.conversation-name :deep(.el-input__inner){font-size:24px;font-weight:700;color:#26334d}.conversation-name :deep(.el-input__inner::placeholder){color:#b9c1d1;font-weight:500}.activity-select{width:250px}
.conversation{flex:1;min-height:260px;overflow-y:auto;padding:20px 10px}.message-block{max-width:850px;margin:0 auto 26px}
.msg-row{display:flex;align-items:flex-start;gap:10px;margin-bottom:14px}
.msg-row.user{justify-content:flex-end}
.bubble{max-width:70%;padding:11px 15px;border-radius:14px;font-size:15px;line-height:1.6;color:#364152}
.user-bubble{background:#e8efff;color:#2f3f63;border-top-right-radius:4px}
.avatar{flex:none;font-size:13px;font-weight:600}
.user-avatar{background:#3a5bff;color:#fff}
.ai-avatar{background:#e8efff;color:#3a5bff}
.answer-card{flex:1;border:1px solid #e1e8f5;border-radius:14px;background:#fff;border-top-left-radius:4px}.ans-head{display:flex;align-items:center;gap:9px;margin-bottom:10px}.answer-label{font-weight:700;color:#33415c}.fid{font-size:12px;color:#9aa4b5}.ans-body{white-space:pre-wrap;line-height:1.8;color:#4a5568;margin-bottom:10px}
.tools{display:flex;align-items:center;gap:16px;padding-top:4px}
.tool{font-size:16px;color:#9aa4b5;cursor:pointer;transition:color .15s}
.tool:hover{color:#3a5bff}
.tool.on{color:#3a5bff}
.tool.emoji{font-size:15px;filter:grayscale(1);opacity:.65;line-height:1}
.tool.emoji:hover{filter:none;opacity:1}
.tool.emoji.on{filter:none;opacity:1}
.composer{max-width:900px;width:100%;margin:0 auto;border:1px solid #cdd9f0;border-radius:16px;padding:12px 14px;background:#fff;box-shadow:0 7px 24px rgba(58,91,255,.1);box-sizing:border-box}.composer :deep(.el-textarea__inner){border:0;box-shadow:none;padding:4px;line-height:1.6}.composer-footer{display:flex;justify-content:space-between;align-items:center;margin-top:7px}.hint{font-size:12px;color:#9aa4b5}
.pick-list{max-height:260px;overflow-y:auto;width:100%}.pick-item{display:flex;margin:0 0 6px;width:100%}
@media(max-width:800px){.sidebar{width:180px;flex-basis:180px}.qa-main{padding:22px 20px}.activity-select{width:190px}}@media(max-width:600px){.sidebar{display:none}.qa-main{padding:20px 14px}.qa-head{display:block}.activity-select{width:100%;margin-top:14px}}
</style>
