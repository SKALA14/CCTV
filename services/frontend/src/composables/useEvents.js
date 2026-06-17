// 이벤트 목록·검색 로딩 상태 composable
import { ref } from 'vue'
import { DUMMY_MODE } from '../constants/mode.js'
import { DUMMY_EVENTS } from '../constants/dummyData.js'
import { fetchEvents, searchEvents } from '../api/events.js'

export function useEvents() {
  const events        = ref([])
  const loading       = ref(false)
  const error         = ref(null)
  const appliedFilter = ref(null)

  async function load(params = {}) {
    if (DUMMY_MODE) {
      events.value = DUMMY_EVENTS
      return
    }
    loading.value = true
    error.value   = null
    try {
      const res    = await fetchEvents(params)
      events.value = Array.isArray(res) ? res : (res.events ?? [])
    } catch (e) {
      error.value = e.response?.data?.detail ?? e.message
    } finally {
      loading.value = false
    }
  }

  async function search(query, channelId = null, startDate = null, endDate = null, skipTimeParse = false, siteId = null) {
    if (DUMMY_MODE) {
      const q = (query || '').trim().toLowerCase()
      events.value = DUMMY_EVENTS.filter(ev => {
        const matchChannel = !channelId || ev.camera_id === channelId
        const matchText    = !q || [ev.description, ev.event_type, ev.channel_name]
          .some(s => s && s.toLowerCase().includes(q))
        return matchChannel && matchText
      })
      return
    }
    loading.value       = true
    error.value         = null
    appliedFilter.value = null
    try {
      const res           = await searchEvents(query, channelId, startDate, endDate, skipTimeParse, siteId)
      events.value        = Array.isArray(res) ? res : (res.events ?? [])
      appliedFilter.value = res.applied_filter ?? null
    } catch (e) {
      error.value = e.response?.data?.detail ?? e.message
    } finally {
      loading.value = false
    }
  }

  return { events, loading, error, appliedFilter, load, search }
}
