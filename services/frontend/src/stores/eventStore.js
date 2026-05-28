import { defineStore } from 'pinia'
import { ref } from 'vue'
import { TOAST_DURATION } from '../constants/events.js'

export const NOTIF_DURATION = 10000

const INCIDENT_GAP_MS = 10_000 // 10초 동안 탐지 없으면 사건 종료
const _lastSeenMap = new Map() // key: `${camera_id}:${event_type}`

function _normalizeEventType(type) {
    return type === 'smoke' ? 'fire' : type
}

function _isNewIncident(event) {
    const key = `${event.channel_id || event.camera_id}:${_normalizeEventType(event.event_type)}`
    const now = Date.now()
    const last = _lastSeenMap.get(key) || 0
    _lastSeenMap.set(key, now)
    return now - last > INCIDENT_GAP_MS
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
        if (!_isNewIncident(event)) return

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
