import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChannelStore = defineStore('channel', () => {
    const slots = ref([null, null, null, null])

    function addChannel(channel) {
        if (channels.value.length >= 4) return
        channels.value.push({ ...channel, id: Date.now(), status: 'ok' })
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