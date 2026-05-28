import { ref, onUnmounted } from 'vue'

export function useWebRTCPublish() {
  const status = ref('idle')
  const error  = ref(null)
  const localStream = ref(null)
  let pc = null

  async function startPublish(whipUrl, videoEl = null) {
    try {
      status.value = 'publishing'
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      localStream.value = stream

      if (videoEl) {
        videoEl.srcObject = stream
        videoEl.play().catch(() => {})
      }

      pc = new RTCPeerConnection()
      stream.getTracks().forEach(track => pc.addTrack(track, stream))

      const offer = await pc.createOffer()
      await pc.setLocalDescription(offer)

      await Promise.race([
        new Promise(resolve => {
          if (pc.iceGatheringState === 'complete') { resolve(); return }
          pc.onicegatheringstatechange = () => {
            if (pc.iceGatheringState === 'complete') resolve()
          }
        }),
        new Promise((_, reject) => setTimeout(() => reject(new Error('ICE 타임아웃')), 5000)),
      ])

      const res = await fetch(whipUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/sdp' },
        body: pc.localDescription.sdp,
      })
      if (!res.ok) throw new Error(`WHIP 실패: ${res.status}`)
      const answerSdp = await res.text()
      await pc.setRemoteDescription({ type: 'answer', sdp: answerSdp })
    } catch (e) {
      status.value = 'error'
      error.value = e.message
    }
  }

  function stopPublish() {
    localStream.value?.getTracks().forEach(t => t.stop())
    pc?.close()
    pc = null
    localStream.value = null
    status.value = 'idle'
  }

  onUnmounted(stopPublish)
  return { status, error, localStream, startPublish, stopPublish }
}
