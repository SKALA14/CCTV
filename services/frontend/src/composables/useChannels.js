import { useChannelStore } from '../stores/channelStore.js'
import { storeToRefs } from 'pinia'

export function useChannels() {
    const store = useChannelStore()
    const { slots } = storeToRefs(store)

    return {
        slots,
        addChannel: store.addChannel,
        removeChannel: store.removeChannel,
        updateChannel: store.updateChannel,
    }
}