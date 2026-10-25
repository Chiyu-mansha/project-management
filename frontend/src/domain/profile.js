import { reactive, ref } from 'vue'

export const PROFILE_LABELS = Object.freeze({
  major: '专业', grade: '年级', interests: '兴趣', skills: '技能',
  need_comprehensive_score: '需要综合素养评定积分',
  need_conduct_score: '需要操行分', need_innovation_score: '需要创新分'
})
const emptyProfile = () => Object.fromEntries(Object.keys(PROFILE_LABELS).map(key => [key, key.startsWith('need_') ? 0 : '']))

function readProfile(data) {
  const profile = emptyProfile()
  for (const key of Object.keys(profile)) {
    // New accounts store unset profile fields as SQL NULL.
    const value = data?.[key] === null ? profile[key] : data?.[key]
    if (key.startsWith('need_') ? ![0, 1].includes(value) : typeof value !== 'string') {
      throw new Error('画像数据格式异常，请重新加载')
    }
    profile[key] = value
  }
  return profile
}

export function useProfile(api, getStudentId) {
  const form = reactive(emptyProfile())
  const profile = ref(emptyProfile())
  const editing = ref(false)
  const loaded = ref(false)
  const loading = ref(false)
  const saving = ref(false)
  const error = ref('')
  let revision = 0
  let controller

  function reset() {
    ++revision
    controller?.abort()
    editing.value = loaded.value = loading.value = saving.value = false
    error.value = ''
    profile.value = emptyProfile()
    Object.assign(form, emptyProfile())
  }

  async function load() {
    const id = getStudentId()
    if (!id || saving.value) return
    controller?.abort()
    controller = new AbortController()
    const ticket = ++revision
    loading.value = true
    loaded.value = false
    editing.value = false
    error.value = ''
    try {
      const data = readProfile(await api.getProfile(id, controller.signal))
      if (ticket !== revision) return
      profile.value = data
      Object.assign(form, data)
      loaded.value = true
    } catch (cause) {
      if (ticket === revision && cause.name !== 'AbortError') error.value = cause.message
    } finally {
      if (ticket === revision) loading.value = false
    }
  }

  function edit() {
    if (!loaded.value || loading.value || saving.value) return
    Object.assign(form, profile.value)
    error.value = ''
    editing.value = true
  }

  async function save() {
    const id = getStudentId()
    if (!id || !loaded.value || !editing.value || saving.value) return false
    controller?.abort()
    controller = new AbortController()
    const ticket = ++revision
    saving.value = true
    error.value = ''
    let committed = false
    try {
      const body = readProfile(form)
      await api.updateProfile(id, body, controller.signal)
      if (ticket !== revision) return false
      committed = true
      editing.value = false
      loaded.value = false
      const data = readProfile(await api.getProfile(id, controller.signal))
      if (ticket !== revision) return false
      profile.value = data
      Object.assign(form, data)
      loaded.value = true
      return true
    } catch (cause) {
      if (ticket === revision && cause.name !== 'AbortError') {
        error.value = committed ? `画像已保存，但重新加载失败：${cause.message}。请点击重新加载。` : cause.message
      }
      return false
    } finally {
      if (ticket === revision) saving.value = false
    }
  }

  return { form, profile, editing, loaded, loading, saving, error, reset, load, edit, save }
}
