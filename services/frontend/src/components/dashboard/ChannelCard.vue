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
        v-if="status === 'error'"
        class="flex flex-col items-center justify-center gap-1"
        style="position:absolute; inset:0; background:rgba(0,0,0,0.7);"
      >
        <span class="text-2xl">🚫</span>
        <span class="text-xs text-center" style="color:#fff;">
          {{ error || '스트림 연결 실패' }}
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
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { useWebRTC } from '../../composables/useWebRTC.js'
import { useWebRTCPublish } from '../../composables/useWebRTCPublish.js'
import { useChannelStore } from '../../stores/channelStore.js'
import { MEDIAMTX_URL } from '../../constants/mediamtx.js'

const props = defineProps({ channel: Object })
defineEmits(['edit', 'remove'])

const channelStore = useChannelStore()
const isAlert  = computed(() => props.channel.status === 'alert')
const isWebcam = computed(() => props.channel.sourceType === 'webcam' || props.channel.url === 'webcam')

function extractYoutubeId(url) {
  const patterns = [/[?&]v=([^&#]+)/, /youtu\.be\/([^?&#]+)/]
  for (const p of patterns) {
    const m = url.match(p)
    if (m) return m[1]
  }
  return null
}

const youtubeEmbedUrl = computed(() => {
  if (props.channel.sourceType !== 'youtube') return null
  const id = extractYoutubeId(props.channel.url)
  return id ? `https://www.youtube.com/embed/${id}?autoplay=1&mute=1` : null
})

const { videoRef, status, error, connect, disconnect } = useWebRTC(
  `${MEDIAMTX_URL}/${props.channel.channelName}/whep`
)
const { startPublish, stopPublish } = useWebRTCPublish()

function startStream() {
  const { url, sourceType, channelName } = props.channel
  if (isWebcam.value) {
    startPublish(`/webrtc/${channelName}/whip`, videoRef.value).catch(() => {})
  } else if (sourceType === 'rtsp') {
    connect()
  } else if (sourceType === 'file') {
    videoRef.value.src = `/sample/${url.replace(/^\/?(sample\/)?/, '')}`
  }
}

onMounted(startStream)

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

watch(() => props.channel.url, () => {
  stopPublish()
  disconnect()
  startStream()
})
</script>
