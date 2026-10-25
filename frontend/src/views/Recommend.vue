<script setup>
import { computed, onBeforeUnmount, watch } from 'vue'
import { createApiClient } from '../api/request.js'
import { createRecommendApi } from '../api/recommend.js'
import { session, clearSession } from '../auth/session.js'
import { PREFERENCE_LABELS, useRecommendations } from '../domain/recommendations.js'
import RecommendCards from './RecommendCards.vue'

const student = computed(() => session.value?.role === 'student')
const api = createRecommendApi(createApiClient({
  baseUrl: import.meta.env.VITE_API_BASE_URL || '/api',
  getToken: () => session.value?.token,
  onUnauthorized: clearSession
}))
const { tags, hasFilter, items, total, page, pageSize, loading, scoring,
  listError, scoreError, needsProfile, load, score, reset } = useRecommendations(api, () => student.value)
watch(() => [session.value?.token, session.value?.id, session.value?.role], () => {
  reset()
  if (student.value) score()
}, { immediate: true })
onBeforeUnmount(reset)
</script>

<template>
  <section class="recommend-page" :aria-busy="scoring || loading">
    <div class="page-heading">
      <h2>智能推荐</h2>
      <el-button @click="$router.push('/browse')">去活动广场</el-button>
    </div>
    <el-empty v-if="!student" description="请先以学生身份登录">
      <el-button type="primary" @click="$router.push('/login')">去登录</el-button>
    </el-empty>
    <template v-else>
      <el-alert v-if="scoreError" :title="scoreError" type="error" show-icon :closable="false" class="feedback">
        <el-button v-if="needsProfile" size="small" @click="$router.push('/profile')">完善画像</el-button>
        <el-button size="small" :loading="scoring" @click="score">重试打分</el-button>
        <p>可以先去活动广场查看活动；已有评分仍可通过标签筛选查看。</p>
      </el-alert>
      <div class="tags" role="group" aria-label="推荐偏好">
        <span class="tags-label">筛选标签：</span>
        <el-checkbox v-for="(label, key) in PREFERENCE_LABELS" :key="key" v-model="tags[key]" @change="load(1)">{{ label }}</el-checkbox>
        <el-button size="small" :loading="scoring" @click="score">重新打分</el-button>
      </div>
      <p v-if="scoring" role="status">正在更新匹配评分，完成后将按当前标签展示推荐。</p>
      <el-skeleton v-if="loading" :rows="5" animated />
      <el-alert v-else-if="listError" :title="listError" type="error" show-icon :closable="false">
        <el-button size="small" @click="load(page)">重试推荐列表</el-button>
      </el-alert>
      <el-empty v-else-if="!hasFilter" description="勾选上方标签后，为你筛选推荐活动" />
      <template v-else-if="!scoring">
        <el-empty v-if="!items.length" description="暂无符合条件的推荐">
          <el-button type="primary" @click="$router.push('/browse')">去活动广场</el-button>
        </el-empty>
        <template v-else>
          <p class="muted">共 {{ total }} 个推荐活动{{ scoreError ? '（基于已有评分）' : '' }}</p>
          <slot :items="items" :total="total" :loading="loading">
            <RecommendCards :items="items" />
          </slot>
        </template>
        <el-pagination v-if="total > pageSize" :current-page="page" :page-size="pageSize" :total="total"
          layout="prev, pager, next" @current-change="load" />
      </template>
    </template>
  </section>
</template>

<style scoped>
.recommend-page{max-width:1100px;margin:0 auto}
.page-heading{display:flex;align-items:center;justify-content:space-between;gap:16px;flex-wrap:wrap}
.page-heading h2{margin:0}
.tags{display:flex;flex-wrap:wrap;align-items:center;gap:12px;margin:20px 0}
.tags-label,.muted{color:#606266;font-size:14px}
.feedback{margin-top:16px}
.el-pagination{margin-top:24px;justify-content:center}
</style>
