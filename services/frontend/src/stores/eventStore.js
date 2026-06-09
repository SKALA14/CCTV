import { defineStore } from 'pinia'
import { ref } from 'vue'
import { TOAST_DURATION } from '../constants/events.js'
import { useChannelStore } from './channelStore.js'

export const NOTIF_DURATION = 10000

const INCIDENT_GAP_MS = 10_000
const _lastSeenMap = new Map()

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
    const notifHistory      = ref([])   // 토스트로 발화된 알림 누적 히스토리
    const lastSearchResults = ref([])

    function pushLiveEvent(event) {
        liveEvents.value.unshift(event)

        toastQueue.value.push(event)
        setTimeout(() => { toastQueue.value.shift() }, TOAST_DURATION)

        const level = event.danger_level
        if (!level || level === 'none' || event.event_type === 'normal') return

        // 채널 alert 상태 갱신 — 이벤트가 올 때마다 타이머 리셋
        const channelStore = useChannelStore()
        const cameraId = String(event.channel_id || event.camera_id || '')
        const slot = channelStore.slots.findIndex(
            s => s && String(s.camera_id || s.channelName || '') === cameraId
        )
        if (slot !== -1) {
            const alertLvl = event.pipeline === 'emergency' ? 'emergency'
                : (level === 'high' || level === 'medium') ? 'warning' : null
            if (alertLvl) channelStore.setAlertLevel(slot, alertLvl)
        }

        if (!_isNewIncident(event)) return

        const id = `${Date.now()}-${Math.random()}`
        const notif = { ...event, _notifId: id }

        notifications.value.unshift(notif)
        if (notifications.value.length > 5) notifications.value.pop()
        setTimeout(() => dismissNotification(id), NOTIF_DURATION)

        // 히스토리에는 영구 누적 (최대 200건)
        notifHistory.value.unshift(notif)
        if (notifHistory.value.length > 200) notifHistory.value.pop()
    }

    function dismissNotification(id) {
        notifications.value = notifications.value.filter(n => n._notifId !== id)
    }

    function clearHistory() {
        notifHistory.value = []
    }

    function setSearchResults(results) {
        lastSearchResults.value = results
    }

    return {
        liveEvents, toastQueue, notifications, notifHistory, lastSearchResults,
        pushLiveEvent, dismissNotification, clearHistory, setSearchResults,
    }
})
