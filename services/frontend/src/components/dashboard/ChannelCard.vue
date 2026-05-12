<template>
  <div class="channel-card" :class="{ 'alert-state': isAlert }">
    <div class="status-badge" :class="isAlert ? 'badge-alert' : 'badge-ok'">
      <span class="status-dot"></span>
      {{ isAlert ? channel.event_type : '정상' }}
    </div>

    <div class="video-area">
      <iframe
        v-if="channel.sourceType === 'youtube' && youtubeEmbedUrl"
        :src="youtubeEmbedUrl"
        allow="autoplay; encrypted-media"
        allowfullscreen
        style="width:100%; height:100%; border:none; border-radius:inherit;"
      />
      <video
        v-else
        ref="videoRef"
        autoplay
        muted
        playsinline
        style="width:100%; height:100%; object-fit:cover; border-radius:inherit;"
      />
      <div
        v-if="status === 'connecting'"
        class="flex flex-col items-center justify-center gap-1"
        style="position:absolute; inset:0; background:rgba(0,0,0,0.6);"
      >
        <span class="text-xs" style="color:#fff;">연결 중...</span>
      </div>
      <div
        v-if="status === 'error' || webcamError"
        class="flex flex-col items-center justify-center gap-1"
        style="position:absolute; inset:0; background:rgba(0,0,0,0.7);"
      >
        <span class="text-2xl">🚫</span>
        <span class="text-xs text-center" style="color:#fff;">
          {{ webcamError ? '웹캠 접근 실패\n브라우저 권한을 확인해주세요' : (error || '스트림 연결 실패') }}
        </span>
      </div>
    </div>

    <div class="hover-actions">
      <button class="hover-btn" @click.stop="$emit('edit', channel)">수정</button>
      <button class="hover-btn" @click.stop="$emit('remove', channel.slot)">삭제</button>
    </div>

    <div class="name-strip">{{ channel.name }}</div>
  </div>
</template>

<script setup>
import { computed, ref, onMounted, onUnmounted, watch } from 'vue'
import { useWebRTC } from '../../composables/useWebRTC.js'
import { useWebRTCPublish } from '../../composables/useWebRTCPublish.js'
import { useChannelStore } from '../../stores/channelStore.js'
import { MEDIAMTX_URL } from '../../constants/mediamtx.js'

const props = defineProps({ channel: Object })
defineEmits(['edit', 'remove'])

const channelStore = useChannelStore()
const isAlert      = computed(() => props.channel.status === 'alert')
const webcamError  = ref(false)  // getUserMedia 실패 시에만 true

function extractYoutubeId(url) {
  const patterns = [
    /[?&]v=([^&#]+)/,
    /youtu\.be\/([^?&#]+)/,
  ]
  for (const pattern of patterns) {
    const m = url.match(pattern)
    if (m) return m[1]
  }
  return null
}

const youtubeEmbedUrl = computed(() => {
  if (props.channel.sourceType !== 'youtube') return null
  const id = extractYoutubeId(props.channel.url)
  return id ? `https://www.youtube.com/embed/${id}?autoplay=1&mute=1` : null
})

function whepUrl(channelName) {
  return `${MEDIAMTX_URL}/${channelName}/whep`
}

const { videoRef, status, error, connect, disconnect } = useWebRTC(
  whepUrl(props.channel.channelName)
)

const { status: pubStatus, startPublish, stopPublish } = useWebRTCPublish()

function isWebcam(ch) {
  return ch.sourceType === 'webcam' || ch.url === 'webcam'
}

onMounted(() => {
  const { url, sourceType } = props.channel
  if (isWebcam(props.channel)) {
    const whipUrl = `/webrtc/${props.channel.channelName}/whip`
    startPublish(whipUrl, videoRef.value).catch(() => {
      // WHIP 실패해도 로컬 프리뷰는 유지
    })
  } else if (sourceType === 'rtsp') {
    connect()
  } else if (sourceType === 'file') {
    videoRef.value.src = `/sample/${url.replace(/^\/?(sample\/)?/, '')}`
  }
})

onUnmounted(() => {
  stopPublish()
  disconnect()
})

watch(status, (newStatus) => {
  if (newStatus === 'error') {
    channelStore.setChannelStatus(props.channel.slot, 'error')
  } else if (newStatus === 'connected') {
    channelStore.setChannelStatus(props.channel.slot, 'ok')
  }
})

watch(() => props.channel.url, (newUrl) => {
  stopPublish()
  disconnect()

  if (isWebcam(props.channel)) {
    const whipUrl = `/webrtc/${props.channel.channelName}/whip`
    startPublish(whipUrl, videoRef.value)
  } else if (props.channel.sourceType === 'rtsp') {
    connect()
  } else if (props.channel.sourceType === 'file') {
    videoRef.value.src = `/sample/${newUrl.replace(/^\/?(sample\/)?/, '')}`
  }
})
</script>
