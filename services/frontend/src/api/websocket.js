const WS_URL = import.meta.env.VITE_WS_URL || `ws://${location.host}/ws`

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

    socket.onclose = (event) => {
        if (event.code === 4001) {
            // JWT 만료/무효 — 재연결 금지, 로그인 페이지로 이동
            console.warn('[WS] 인증 실패 (4001) — 로그인 페이지로 이동')
            if (window.location.pathname !== '/login') {
                window.location.href = '/login'
            }
            return
        }
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