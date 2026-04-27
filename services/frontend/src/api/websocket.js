const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'

let socket = null
const listeners = new Set()

export function connectWS() {
    if (socket?.readyState === WebSocket.OPEN) return

    socket = new WebSocket(WS_URL)

    socket.onmessage = (e) => {
        const data = JSON.parse(e.data)
        listeners.forEach(fn => fn(data))
    }

    socket.onerror = (e) => {
        console.error('[WS] error', e)
    }

    socket.onclose = () => {
        setTimeout(connectWS, 3000)
    }
}

export function onWSMessage(fn) {
    listeners.add(fn)
    return () => listeners.delete(fn)
}

export function closeWS() {
    socket?.close()
}