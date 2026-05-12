import { defineStore } from 'pinia'
import { ref } from 'vue'
import { TOAST_DURATION } from '../constants/events.js'

export const NOTIF_DURATION = 8000

// TODO: 임시 쿨다운 로직 — 추후 별도 파일로 분리 예정
const NOTIF_COOLDOWN_MS = 5 * 60 * 1000 // 5분
const _cooldownMap = new Map() // key: `${camera_id}:${event_type}`

function _isCoolingDown(event) {
    const key = `${event.channel_id || event.camera_id}:${event.event_type}`
    const last = _cooldownMap.get(key) || 0
    if (Date.now() - last < NOTIF_COOLDOWN_MS) return true
    _cooldownMap.set(key, Date.now())
    return false
}

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

        // 우하단 알림 (신규) — 정상 이벤트 및 쿨다운 중인 이벤트 제외
        const level = event.danger_level
        if (!level || level === 'none' || event.event_type === 'normal') return
        if (_isCoolingDown(event)) return

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
