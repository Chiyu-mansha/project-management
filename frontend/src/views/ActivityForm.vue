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
      <el-form-item label="开始时间" required>
        <el-date-picker v-model="form.start_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="选择开始时间" style="width:100%" />
      </el-form-item>
      <el-form-item label="结束时间">
        <el-date-picker v-model="form.end_time" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="选择结束时间" style="width:100%" />
      </el-form-item>
      <el-form-item label="地点" required>
        <el-input v-model="form.location" placeholder="线上活动可填「线上」" />
      </el-form-item>
      <el-form-item label="简介">
        <el-input v-model="form.description" type="textarea" :rows="3" placeholder="活动介绍（推文生成的基础信息）" />
      </el-form-item>
      <el-form-item label="报名条件">
        <el-input v-model="form.requirements" placeholder="如：面向大二及以上" />
      </el-form-item>
      <el-form-item label="标签">
        <el-input v-model="form.tags" placeholder="逗号分隔，如：篮球,体育" />
      </el-form-item>
      <el-form-item label="封面图">
        <div style="display:flex;gap:12px;align-items:flex-start">
          <el-upload :show-file-list="false" :http-request="uploadCover" accept="image/*">
            <img v-if="form.cover_image" :src="form.cover_image" class="cover-preview" alt="封面" />
            <div v-else class="cover-placeholder">+ 上传封面</div>
          </el-upload>
          <el-button @click="openCoverDlg">🎨 AI 生成</el-button>
        </div>
      </el-form-item>
      <el-form-item label="报名截止">
        <el-date-picker v-model="form.signup_deadline" type="datetime" value-format="YYYY-MM-DDTHH:mm:ss" placeholder="选择报名截止时间" style="width:100%" />
      </el-form-item>
      <el-form-item label="组队报名">
        <el-switch v-model="isTeam" active-text="需要组队" inactive-text="个人" />
      </el-form-item>
      <el-form-item v-if="isTeam" label="队伍人数">
        <div style="display:flex;gap:8px;align-items:center">
          <el-input-number v-model="form.min_team_member" :min="1" /> 至
          <el-input-number v-model="form.max_team_member" :min="1" />
        </div>
      </el-form-item>
      <el-form-item label="队伍上限">
        <el-input-number v-model="form.max_participants" :min="0" placeholder="空=不限" style="width:100%" />
      </el-form-item>
      <el-form-item label="发电子票">
        <el-switch v-model="form.has_ticket" :active-value="1" :inactive-value="0" />
      </el-form-item>
      <el-form-item label="综测加分">
        <el-switch v-model="form.comprehensive_score" :active-value="1" :inactive-value="0" active-text="提供" inactive-text="不提供" @change="onScoreSwitch" />
      </el-form-item>
      <el-form-item label="操行分">
        <el-input-number v-model="form.conduct_score" :min="0" :step="0.5" :disabled="form.comprehensive_score !== 1" style="width:100%" />
      </el-form-item>
      <el-form-item label="创新分">
        <el-input-number v-model="form.innovation_score" :min="0" :step="0.5" :disabled="form.comprehensive_score !== 1" style="width:100%" />
      </el-form-item>
      <el-form-item label="状态">
        <el-radio-group v-model="form.status">
          <el-radio-button label="draft" :disabled="!canSet('draft')">草稿</el-radio-button>
          <el-radio-button label="published" :disabled="!canSet('published')">发布</el-radio-button>
          <el-radio-button label="ongoing" :disabled="!canSet('ongoing')">进行中</el-radio-button>
          <el-radio-button label="finished" :disabled="!canSet('finished')">已结束</el-radio-button>
          <el-radio-button label="cancelled" :disabled="!canSet('cancelled')">取消</el-radio-button>
        </el-radio-group>
      </el-form-item>
      <el-form-item>
        <el-button type="primary" :loading="saving" @click="save">{{ isEdit ? '保存修改' : '发布活动' }}</el-button>
        <el-button @click="$router.back()">取消</el-button>
      </el-form-item>
    </el-form>

    <el-dialog v-model="coverDlg" title="🎨 AI 生成封面" width="480px">
      <el-input v-model="coverPrompt" type="textarea" :rows="3" placeholder="描述你想要的封面，如：青春活力的篮球赛海报，蓝色调" />
      <template #footer>
        <el-button @click="coverDlg = false">取消</el-button>
        <el-button type="primary" :loading="coverLoading" @click="generateCover">生成</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script setup>
import { ref, reactive, computed, onMounted } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { session } from '../auth/session.js'

const API = 'http://localhost:8000'
const TYPES = ['学科类', '文体类', '科创竞赛', '社会实践']
const route = useRoute()
const router = useRouter()
const isEdit = computed(() => !!route.params.id)
const saving = ref(false)

// 状态机：draft -> published -> ongoing -> finished 单向；cancelled 为终态；新建只能草稿/发布
const ALLOWED = {
  draft: ['draft', 'published', 'cancelled'],
  published: ['published', 'cancelled'],
  ongoing: ['ongoing', 'cancelled'],
  finished: ['finished'],
  cancelled: ['cancelled'],
}
const origStatus = ref('draft')
const isTeam = ref(false)
// 进行中/已结束 由时间自动流转，不可手动设置
const canSet = (s) => {
  if (s === 'ongoing' || s === 'finished') return false
  if (!isEdit.value) return ['draft', 'published'].includes(s)
  return ALLOWED[origStatus.value]?.includes(s) ?? false
}

const form = reactive({
  title: '', type: '', organizer_id: null, start_time: '', end_time: '', location: '',
  description: '', requirements: '', tags: '', signup_deadline: '',
  min_team_member: 1, max_team_member: 1, max_participants: null,
  has_ticket: 1, comprehensive_score: 0, conduct_score: null, innovation_score: null,
  cover_image: '', status: 'draft',
})

// 不提供综测加分时，清空分值（输入框同时被禁用）
const onScoreSwitch = () => {
  if (form.comprehensive_score !== 1) {
    form.conduct_score = null
    form.innovation_score = null
  }
}

// 上传封面图
const uploadCover = async ({ file }) => {
  const fd = new FormData()
  fd.append('file', file)
  try {
    const r = await fetch(`${API}/api/upload`, { method: 'POST', body: fd })
    const d = await r.json()
    if (d.code === 0) {
      form.cover_image = `${API}${d.data.url}`
      ElMessage.success('封面已上传')
    } else {
      ElMessage.error(d.message || '上传失败')
    }
  } catch {
    ElMessage.error('上传失败')
  }
}

// AI 生成封面
const coverDlg = ref(false)
const coverPrompt = ref('')
const coverLoading = ref(false)

const openCoverDlg = () => {
  coverPrompt.value = `${form.title || '校园活动'}${form.type ? '，' + form.type : ''}主题海报，简洁现代风格`
  coverDlg.value = true
}

const generateCover = async () => {
  if (!coverPrompt.value.trim()) return ElMessage.warning('请输入封面描述')
  coverLoading.value = true
  try {
    const r = await fetch(`${API}/api/activities/generate-cover`, {
      method: 'POST', headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ prompt: coverPrompt.value }),
    })
    const d = await r.json()
    if (d.code === 0) {
      form.cover_image = `${API}${d.data.url}`
      ElMessage.success('封面已生成')
      coverDlg.value = false
    } else {
      ElMessage.error(d.message || '生成失败')
    }
  } catch {
    ElMessage.error('生成失败')
  } finally {
    coverLoading.value = false
  }
}

onMounted(async () => {
  if (isEdit.value) {
    const d = await (await fetch(`${API}/api/activities/${route.params.id}`)).json()
    origStatus.value = d.data?.status || 'draft'
    isTeam.value = (d.data?.max_team_member || 1) > 1
    Object.assign(form, d.data)
  }
})

const save = async () => {
  if (!form.title.trim()) return ElMessage.error('活动标题必填')
  if (!form.start_time) return ElMessage.error('请选择开始时间')
  if (!form.location.trim()) return ElMessage.error('请填写地点')
  if (!isTeam.value) { form.min_team_member = 1; form.max_team_member = 1 }
  if (form.max_team_member < form.min_team_member) return ElMessage.error('最多人数不能小于最少人数')
  // 发布者发布活动时自动关联当前登录的 organizer_id
  if (session.value?.role === 'organizer' && form.organizer_id == null) {
    form.organizer_id = session.value.id
  }
  saving.value = true
  try {
    const url = isEdit.value ? `${API}/api/activities/${route.params.id}` : `${API}/api/activities`
    const r = await fetch(url, { method: isEdit.value ? 'PUT' : 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(form) })
    if (!r.ok) {
      const e = await r.json().catch(() => ({}))
      return ElMessage.error(e.message || '保存失败')
    }
    ElMessage.success(isEdit.value ? '已保存' : '发布成功')
    router.push('/activities')
  } finally {
    saving.value = false
  }
}
</script>

<style scoped>
.form-wrap{max-width:680px;margin:0 auto}
.head{margin:0 0 18px;font-size:20px}
.cover-preview{width:200px;height:112px;object-fit:cover;border-radius:8px;display:block}
.cover-placeholder{width:200px;height:112px;border:1px dashed #d9d9d9;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#999;cursor:pointer}
</style>
