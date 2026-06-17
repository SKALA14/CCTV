// 채널 스토어를 컴포넌트에서 쓰기 위한 composable
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