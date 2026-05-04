import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useChannelStore = defineStore('channel', () => {
    const channels = ref([])

    function addChannel(channel) {
        if (channels.value.length >= 4) return
        const streamId = channel.url.split('/').pop()
        channels.value.push({ ...channel, id: streamId, status: 'ok' })
    }

    function removeChannel(id) {
        channels.value = channels.value.filter(c => c.id !== id)
    }

    function updateChannel(id, patch) {
        const idx = channels.value.findIndex(c => c.id === id)
        if (idx !== -1) channels.value[idx] = { ...channels.value[idx], ...patch }
    }

    function setChannelStatus(id, status) {
        updateChannel(id, { status })
    }

    return { channels, addChannel, removeChannel, updateChannel, setChannelStatus }
})