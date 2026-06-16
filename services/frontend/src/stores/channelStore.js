// 채널 슬롯 전역 상태 — 그리드 슬롯·경고 점등 관리
import { defineStore } from 'pinia'
import { ref } from 'vue'

const ALERT_CLEAR_MS = 30_000
const _alertTimers = new Map()

export const useChannelStore = defineStore('channel', () => {
    const slots = ref([null, null, null, null])

    function addChannel(slot, data) {
        slots.value[slot] = {
            slot,
            camera_id:   `cam${slot}`,
            channelName: data.channelName ?? `cam${slot}`,
            ...data,
            status: 'ok',
        }
    }

    function removeChannel(slot) {
        slots.value[slot] = null
    }

    function updateChannel(slot, patch) {
        if (slots.value[slot]) {
            slots.value[slot] = { ...slots.value[slot], ...patch }
        }
    }

    function setChannelStatus(slot, status) {
        updateChannel(slot, { status })
    }

    function resetSlots() {
        slots.value = [null, null, null, null]
    }

    // 이벤트가 올 때마다 호출. 30초 동안 새 이벤트 없으면 자동 해제.
    function setAlertLevel(slot, level) {
        updateChannel(slot, { alertLevel: level })
        if (_alertTimers.has(slot)) clearTimeout(_alertTimers.get(slot))
        _alertTimers.set(slot, setTimeout(() => {
            updateChannel(slot, { alertLevel: null })
            _alertTimers.delete(slot)
        }, ALERT_CLEAR_MS))
    }

    return { slots, addChannel, removeChannel, updateChannel, setChannelStatus, resetSlots, setAlertLevel }
})