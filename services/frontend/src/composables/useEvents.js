import { ref } from 'vue'
import { DUMMY_MODE } from '../constants/mode.js'
import { DUMMY_EVENTS } from '../constants/dummyData.js'
import { fetchEvents, searchEvents } from '../api/events.js'

export function useEvents() {
  const events = ref([])
  const loading = ref(false)
  const error = ref(null)

  async function load(params = {}) {
    if (DUMMY_MODE) {
      events.value = DUMMY_EVENTS
      return
    }
    loading.value = true
    error.value = null
    try {
      events.value = await fetchEvents(params)
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  async function search(query, channelId = null) {
    if (DUMMY_MODE) {
      const q = (query || '').trim().toLowerCase()
      events.value = DUMMY_EVENTS.filter(ev => {
        const matchChannel = !channelId || ev.channel_id === channelId
        const matchText = !q || [ev.reason, ev.event_type, ev.channel_name]
          .some(s => s && s.toLowerCase().includes(q))
        return matchChannel && matchText
      })
      return
    }
    loading.value = true
    error.value = null
    try {
      events.value = await searchEvents(query, channelId)
    } catch (e) {
      error.value = e.message
    } finally {
      loading.value = false
    }
  }

  return { events, loading, error, load, search }
}
