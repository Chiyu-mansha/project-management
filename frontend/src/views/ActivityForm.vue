<template>
  <div class="form-wrap">
    <h3 class="head">{{ isEdit ? '编辑活动' : '发布活动' }}</h3>
    <el-form :model="form" label-width="110px">
      <el-form-item label="活动标题" required>
        <el-input v-model="form.title" placeholder="必填" />
      </el-form-item>
      <el-form-item label="活动类型">
        <el-select v-model="form.type" filterable allow-create default-first-option placeholder="选择或输入" style="width:100%">
          <el-option v-for="t in TYPES" :key="t" :label="t" :value="t" />
        </el-select>
      </el-form-item>
      <el-form-item label="主办方"><el-input v-model="form.organizer" /></el-form-item>
      <el-form-item label="简介"><el-input v-model="form.description" type="textarea" :rows="3" /></el-form-item>
      <el-form-item label="标签"><el-input v-model="form.tags" placeholder="逗号分隔，如：篮球,体育" /></el-form-item>
      <el-form-item label="地点"><el-input v-model="form.location" /></el-form-item>
      <el-form-item label="开始时间"><el-date-picker v-model="form.start_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="选择开始时间" style="width:100%" /></el-form-item>
      <el-form-item label="结束时间"><el-date-picker v-model="form.end_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="选择结束时间" style="width:100%" /></el-form-item>
      <el-form-item label="报名截止"><el-date-picker v-model="form.signup_deadline" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="选择报名截止时间" style="width:100%" /></el-form-item>
      <el-form-item label="人数上限"><el-input-number v-model="form.max_participants" :min="0" style="width:100%" /></el-form-item>
      <el-form-item label="发电子票"><el-switch v-model="form.has_ticket" :active-value="1" :inactive-value="0" /></el-form-item>
      <el-form-item label="综测加分"><el-input v-model="form.zongce_score" placeholder="如：+2 综测分" /></el-form-item>
      <el-form-item label="状态">
        <el-radio-group v-model="form.status">
          <el-radio-button label="draft" :disabled="!canSet('draft')">草稿</el-radio-button>
          <el-radio-button label="published" :disabled="!canSet('published')">发布</el-radio-button>
          <el-radio-button label="cancelled" :disabled="!canSet('cancelled')">取消</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="save">{{ isEdit ? '保存修改' : '发布活动' }}</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'

const API = 'http://localhost:8000'
const TYPES = ['讲座', '竞赛', '文体', '社会实践', '科创', '招募']
const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const saving = ref(false)
// 状态只能前进：draft -> published -> cancelled，不能后退；新建不允许直接取消
const RANK = { draft: 0, published: 1, cancelled: 2 }
const origStatus = ref('draft')
const canSet = (s) => (!isEdit.value ? s !== 'cancelled' : RANK[s] >= RANK[origStatus.value])

const form = reactive({
  title: '', description: '', organizer: '', type: '', tags: '', location: '',
  start_time: '', end_time: '', signup_deadline: '', max_participants: null,
  has_ticket: 0, zongce_score: '', status: 'draft',
})

onMounted(async () => {
  if (isEdit.value) {
    const d = await (await fetch(`${API}/api/activities/${route.params.id}`)).json()
    origStatus.value = d.status || 'draft'
    Object.assign(form, d)
  }
})

const save = async () => {
  if (!form.title.trim()) return ElMessage.error('活动标题必填')
  saving.value = true
  try {
    const url = isEdit.value ? `${API}/api/activities/${route.params.id}` : `${API}/api/activities`
    const r = await fetch(url, { method: isEdit.value ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) })
    if (!r.ok) return ElMessage.error('保存失败')
    ElMessage.success(isEdit.value ? '已保存' : '发布成功')
    router.push('/activities')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.form-wrap{max-width:640px;margin:0 auto}
.head{margin:0 0 18px;font-size:20px}
</style>
