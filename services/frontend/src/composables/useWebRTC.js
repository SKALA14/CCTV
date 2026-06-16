// MediaMTX WHEP 영상 수신(구독) composable — 재연결 포함
import { ref, onUnmounted } from 'vue'

const RETRY_LIMIT    = 10
const RETRY_DELAY_MS = 2000

export function useWebRTC(whepUrl) {
  const videoRef = ref(null)
  const status   = ref('disconnected')
  const error    = ref(null)

  let pc          = null
  let retryTimer  = null
  let retryCount  = 0
 
  async function connect() {
    if (pc) disconnect()

    status.value = 'connecting'
    error.value  = null

    try {
      pc = new RTCPeerConnection()

      pc.addTransceiver('video', { direction: 'recvonly' })
      pc.addTransceiver('audio', { direction: 'recvonly' })

      pc.ontrack = (e) => {
        if (e.track.kind === 'video' && videoRef.value) {
          if (!videoRef.value.srcObject) {
            videoRef.value.srcObject = new MediaStream()
          }
          videoRef.value.srcObject.addTrack(e.track)
          status.value = 'connected'
          retryCount   = 0
        }
      }

      pc.onconnectionstatechange = () => {
        if (pc.connectionState === 'failed' || pc.connectionState === 'closed') {
          status.value = 'error'
          error.value  = 'WebRTC 연결이 끊어졌습니다.'
        }
      }

      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      await new Promise((resolve) => {
        if (pc.iceGatheringState === 'complete') { resolve(); return }
        pc.onicegatheringstatechange = () => {
          if (pc.iceGatheringState === 'complete') resolve()
        }
      })

      const res = await fetch(whepUrl, {
        method:  'POST',
        headers: { 'Content-Type': 'application/sdp' },
        body:    pc.localDescription.sdp,
      })

      if (res.status === 404 || res.status === 503) {
        disconnect()
        scheduleRetry()
        return
      }

      if (!res.ok) throw new Error(`WHEP 응답 오류: ${res.status}`)

      const answerSdp = await res.text()
      await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp })
    } catch (e) {
      status.value = 'error'
      error.value  = e.message
      disconnect()
    }
  }

  function scheduleRetry() {
    if (retryCount >= RETRY_LIMIT) {
      status.value = 'error'
      error.value  = '스트림에 연결할 수 없습니다.'
      return
    }
    retryCount++
    retryTimer = setTimeout(connect, RETRY_DELAY_MS)
  }

  function disconnect() {
    clearTimeout(retryTimer)
    pc?.close()
    pc = null
    if (videoRef.value) {
      videoRef.value.srcObject = null
    }
    if (status.value !== 'error') status.value = 'disconnected'
  }

  onUnmounted(disconnect)

  return { videoRef, status, error, connect, disconnect }
}
