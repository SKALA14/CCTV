import { defineStore } from 'pinia'
import { ref } from 'vue'

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

    return { slots, addChannel, removeChannel, updateChannel, setChannelStatus }
})