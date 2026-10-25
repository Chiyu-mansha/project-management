import { computed, reactive, ref } from 'vue'

export const PREFERENCE_LABELS = Object.freeze({
  match_major: '专业匹配', match_interests: '兴趣', match_skills: '技能锻炼',
  need_conduct_score: '操行分', need_innovation_score: '创新分',
  need_comprehensive_score: '综合素养评定积分'
})

export function readRecommendations(data) {
  if (!Array.isArray(data?.items) || !Number.isSafeInteger(data.total) || data.total < data.items.length ||
      data.items.some(item => !Number.isSafeInteger(item?.activity_id) || item.activity_id < 1 ||
        !Array.isArray(item.reasons) || item.reasons.some(reason => typeof reason !== 'string'))) {
    throw new Error('推荐结果格式异常，请稍后重试')
  }
  return data
}

// A revision check also handles transports which cannot abort in time.
export function useRecommendations(api, isStudent) {
  const tags = reactive(Object.fromEntries(Object.keys(PREFERENCE_LABELS).map(key => [key, false])))
  const hasFilter = computed(() => Object.values(tags).some(Boolean))
  const items = ref([])
  const total = ref(0)
  const page = ref(1)
  const pageSize = 20
  const loading = ref(false)
  const scoring = ref(false)
  const listError = ref('')
  const scoreError = ref('')
  const needsProfile = ref(false)
  let listVersion = 0
  let scoreVersion = 0
  let listController
  let scoreController

  function clearList() {
    ++listVersion
    listController?.abort()
    items.value = []
    total.value = 0
    loading.value = false
    listError.value = ''
  }

  async function load(nextPage = 1) {
    clearList()
    page.value = nextPage
    if (!isStudent() || !hasFilter.value || scoring.value) return
    const ticket = listVersion
    listController = new AbortController()
    loading.value = true
    try {
      const query = Object.fromEntries(Object.entries(tags).map(([key, value]) => [key, value ? 1 : 0]))
      const data = readRecommendations(await api.list({ ...query, page: nextPage, page_size: pageSize }, listController.signal))
      if (ticket !== listVersion) return
      if (nextPage > 1 && !data.items.length && data.total <= (nextPage - 1) * pageSize) {
        return await load(Math.max(1, Math.ceil(data.total / pageSize)))
      }
      items.value = data.items
      total.value = data.total
    } catch (cause) {
      if (ticket === listVersion && cause.name !== 'AbortError') listError.value = cause.message
    } finally {
      if (ticket === listVersion) loading.value = false
    }
  }

  async function score() {
    if (!isStudent() || scoring.value) return
    clearList()
    scoreController = new AbortController()
    const ticket = ++scoreVersion
    scoring.value = true
    scoreError.value = ''
    needsProfile.value = false
    let succeeded = false
    try {
      await api.score(scoreController.signal)
      succeeded = true
    } catch (cause) {
      if (ticket === scoreVersion && cause.name !== 'AbortError') {
        scoreError.value = cause.message
        needsProfile.value = cause.code === 400
      }
    } finally {
      if (ticket === scoreVersion) scoring.value = false
    }
    if (succeeded && ticket === scoreVersion) await load(1)
  }

  function reset() {
    ++scoreVersion
    scoreController?.abort()
    scoring.value = false
    scoreError.value = ''
    needsProfile.value = false
    clearList()
    page.value = 1
    for (const key of Object.keys(tags)) tags[key] = false
  }

  return { tags, hasFilter, items, total, page, pageSize, loading, scoring, listError, scoreError, needsProfile, load, score, reset }
}
