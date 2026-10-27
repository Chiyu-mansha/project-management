import { ref } from 'vue'
import { readList } from './model.js'
import { readRecommendations } from './recommendations.js'
import { registrationBlockReason } from './activityAccess.js'

export function useRecommendedActivities(request) {
  const displayItems = ref([])
  const unavailable = ref(0)
  const loading = ref(false)
  const error = ref('')
  let version = 0
  let controller
  function clear() {
    ++version
    controller?.abort()
    displayItems.value = []
    unavailable.value = 0
    loading.value = false
    error.value = ''
  }
  async function load(items) {
    clear()
    if (!items?.length) return
    const ticket = version
    controller = new AbortController()
    loading.value = true
    try {
      readRecommendations({ items, total: items.length })
      const ids = [...new Set(items.map(item => item.activity_id))]
      const activities = []
      // Keep requests bounded even when an external slot consumer passes a long list.
      for (let offset = 0; offset < ids.length; offset += 100) {
        const batch = ids.slice(offset, offset + 100)
        const data = readList(await request('/activities', {
          query: { ids: batch.join(','), page: 1, page_size: 100 }, signal: controller.signal
        }))
        if (ticket !== version) return
        activities.push(...data.items)
      }
      const actMap = new Map(activities.map(activity => [activity.id, activity]))
      // POD-1 returns activities by ID, not recommendation rank. Keep backend recommendation order/reasons.
      displayItems.value = items.map(item => ({ ...item, activity: actMap.get(item.activity_id) }))
        .filter(item => item.activity && !registrationBlockReason(item.activity))
      unavailable.value = items.length - displayItems.value.length
    } catch (cause) {
      if (ticket === version && cause.name !== 'AbortError') error.value = cause.message
    } finally {
      if (ticket === version) loading.value = false
    }
  }
  return { displayItems, unavailable, loading, error, load, clear }
}
