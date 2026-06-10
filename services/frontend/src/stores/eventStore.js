import { defineStore } from 'pinia'
import { ref } from 'vue'
import { TOAST_DURATION } from '../constants/events.js'
import { useChannelStore } from './channelStore.js'

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
    const notifHistory      = ref([])   // 토스트로 발화된 알림 누적 히스토리 (최대 200)
    const lastSearchResults = ref([])

    function pushLiveEvent(event) {
        liveEvents.value.unshift(event)

        // 상단 배너 (기존)
        toastQueue.value.push(event)
        setTimeout(() => { toastQueue.value.shift() }, TOAST_DURATION)

        // 우하단 알림 (신규) — 정상 이벤트 및 쿨다운 중인 이벤트 제외
        const level = event.danger_level
        if (!level || level === 'none' || event.event_type === 'normal') return

        // 채널 카드 경고 점등 — 이벤트가 올 때마다 타이머 리셋(30초 후 자동 해제)
        const channelStore = useChannelStore()
        const cameraId = String(event.channel_id || event.camera_id || '')
        const slot = channelStore.slots.findIndex(
            s => s && String(s.camera_id || s.channelName || '') === cameraId
        )
        if (slot !== -1) {
            // 위험도 체계: emergency 파이프라인=위험(빨강), 일반 critical/high/medium=경고(주황)
            const alertLvl = event.pipeline === 'emergency' ? 'emergency'
                : (level === 'critical' || level === 'high' || level === 'medium') ? 'warning' : null
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
