// WebSocket 수신 이벤트를 eventStore에 연결하는 composable
import { onMounted, onUnmounted } from 'vue'
import { connectWS, onWSMessage, closeWS } from '../api/websocket.js'
import { useEventStore } from '../stores/eventStore.js'

export function useWebSocket() {
    const eventStore = useEventStore()

    let unsubscribe = null

    onMounted(() => {
        connectWS()
        unsubscribe = onWSMessage((data) => {
            if (data.type === 'new_event') {
                eventStore.pushLiveEvent(data.payload)
            }
        })
    })

    onUnmounted(() => {
        unsubscribe?.()
        closeWS()
    })
}