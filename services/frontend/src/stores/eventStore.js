import { defineStore } from 'pinia'
import { ref } from 'vue'
import { TOAST_DURATION } from '../constants/events.js'

export const NOTIF_DURATION = 8000

export const useEventStore = defineStore('event', () => {
    const liveEvents        = ref([])
    const toastQueue        = ref([])
    const notifications     = ref([])
    const lastSearchResults = ref([])

    function pushLiveEvent(event) {
        liveEvents.value.unshift(event)

        // 상단 배너 (기존)
        toastQueue.value.push(event)
        setTimeout(() => { toastQueue.value.shift() }, TOAST_DURATION)

        // 우하단 알림 (신규) — 정상 이벤트는 제외
        const level = event.danger_level
        if (!level || level === 'none' || event.event_type === 'normal') return

        const id = `${Date.now()}-${Math.random()}`
        notifications.value.unshift({ ...event, _notifId: id })
        if (notifications.value.length > 5) notifications.value.pop()
        setTimeout(() => dismissNotification(id), NOTIF_DURATION)
    }

    function dismissNotification(id) {
        notifications.value = notifications.value.filter(n => n._notifId !== id)
    }

    function setSearchResults(results) {
        lastSearchResults.value = results
    }

    return {
        liveEvents, toastQueue, notifications, lastSearchResults,
        pushLiveEvent, dismissNotification, setSearchResults,
    }
})
