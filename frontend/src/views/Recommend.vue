<template>
  <div class="recommend-page">
    <h2>智能推荐</h2>
    <el-empty v-if="!student" description="请先以学生身份登录">
      <el-button type="primary" @click="$router.push('/login')">去登录</el-button>
    </el-empty>
    <template v-else>
      <el-alert v-if="scoreError" :title="scoreError" type="error" show-icon :closable="false">
        <el-button size="small" @click="score">重试打分</el-button>
      </el-alert>

      <div class="tags">
        <span class="tags-label">筛选标签：</span>
        <el-checkbox v-model="tags.match_major" @change="load">专业匹配</el-checkbox>
        <el-checkbox v-model="tags.match_interests" @change="load">兴趣</el-checkbox>
        <el-checkbox v-model="tags.match_skills" @change="load">技能锻炼</el-checkbox>
        <el-checkbox v-model="tags.need_conduct_score" @change="load">操行分</el-checkbox>
        <el-checkbox v-model="tags.need_innovation_score" @change="load">创新分</el-checkbox>
        <el-checkbox v-model="tags.need_comprehensive_score" @change="load">综合素养评定积分</el-checkbox>
        <el-button size="small" :loading="scoring" @click="score">重新打分</el-button>
      </div>

      <el-alert v-if="listError" :title="listError" type="error" show-icon :closable="false" />
      <el-empty v-if="!hasFilter" description="勾选上方标签后，为你筛选推荐活动" />
      <template v-else>
        <!--
          占位接口（POD-1 联调用）：把推荐结果通过作用域插槽交给 POD-1 的活动展示组件渲染。
          POD-1 用法：<Recommend v-slot="{ items, total, loading }">…渲染活动卡片…</Recommend>
          items = [{ activity_id, score, scores: { major, interests, skills }, reasons }]
        -->
        <slot :items="items" :total="total" :loading="loading">
          <el-empty v-if="!loading && items.length === 0" description="暂无符合条件的推荐" />
          <p v-else class="muted">共 {{ total }} 个推荐活动，活动卡片由 POD-1 展示组件渲染。</p>
        </slot>
      </template>
    </template>
  </div>
</template>

<script setup>
import { computed, onMounted, reactive, ref } from 'vue'
import { createApiClient } from '../api/request.js'
import { createRecommendApi } from '../api/recommend.js'
import { session, clearSession } from '../auth/session.js'

const request = createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  getToken: () => session.value?.token,
  onUnauthorized: () => clearSession()
})
const recommendApi = createRecommendApi(request)
const student = computed(() => session.value?.role === 'student')

const tags = reactive({
  match_major: false, match_interests: false, match_skills: false,
  need_conduct_score: false, need_innovation_score: false, need_comprehensive_score: false
})
const scoring = ref(false)
const scoreError = ref('')
const loading = ref(false)
const listError = ref('')
const items = ref([])
const total = ref(0)

const hasFilter = computed(() => Object.values(tags).some(Boolean))

function query() {
  return {
    match_major: tags.match_major ? 1 : 0,
    match_interests: tags.match_interests ? 1 : 0,
    match_skills: tags.match_skills ? 1 : 0,
    need_conduct_score: tags.need_conduct_score ? 1 : 0,
    need_innovation_score: tags.need_innovation_score ? 1 : 0,
    need_comprehensive_score: tags.need_comprehensive_score ? 1 : 0
  }
}

async function score() {
  if (!student.value || scoring.value) return
  scoring.value = true
  scoreError.value = ''
  try {
    await recommendApi.score()
  } catch (cause) {
    scoreError.value = cause.message
  } finally {
    scoring.value = false
  }
  await load()
}

let revision = 0
async function load() {
  if (!student.value || !hasFilter.value) {
    items.value = []
    total.value = 0
    return
  }
  const ticket = ++revision
  loading.value = true
  listError.value = ''
  try {
    const data = await recommendApi.list(query())
    if (ticket !== revision) return
    items.value = data.items
    total.value = data.total
  } catch (cause) {
    if (ticket === revision) listError.value = cause.message
  } finally {
    if (ticket === revision) loading.value = false
  }
}

onMounted(score)
</script>

<style scoped>
.recommend-page{max-width:900px}
.tags{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin:16px 0}
.tags-label{color:#606266;font-size:14px}
.muted{color:#909399;font-size:13px;margin-top:10px}
</style>
