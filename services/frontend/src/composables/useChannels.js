import { computed } from 'vue'
import { useChannelStore } from '../stores/channelStore.js'
import { storeToRefs } from 'pinia'
import { DUMMY_MODE } from '../constants/mode.js'
import { DUMMY_CHANNELS } from '../constants/dummyData.js'

export function useChannels() {
  const store = useChannelStore()
  const { channels: storeChannels } = storeToRefs(store)

  const channels = computed(() => DUMMY_MODE ? DUMMY_CHANNELS : storeChannels.value)

  return {
    channels,
    addChannel: store.addChannel,
    removeChannel: store.removeChannel,
    updateChannel: store.updateChannel,
  }
}
