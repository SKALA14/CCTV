<!-- 채널 카드 — 영상 + 상태 배지 -->
<template>
  <div class="channel-card" :class="cardStateClass">
    <div class="status-badge" :class="badgeClass">
      <span class="status-dot"></span>
      {{ badgeText }}
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

    <div v-if="canEdit" class="hover-actions">
      <button class="hover-btn" @click.stop="$emit('edit', channel)">수정</button>
      <button class="hover-btn" @click.stop="$emit('remove', channel.slot)">삭제</button>
    </div>

    <div class="name-strip">
      <div>{{ channel.name }}</div>
      <div v-if="lastEvent" class="text-[10px] mt-0.5" style="color: rgba(255,255,255,0.45);">
        {{ lastEvent.event_type }} · {{ formatEventTime(lastEvent.timestamp) }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { computed, onMounted, onUnmounted, watch } from 'vue'
import { storeToRefs } from 'pinia'
import { useWebRTC } from '../../composables/useWebRTC.js'
import { useWebRTCPublish } from '../../composables/useWebRTCPublish.js'
import { useChannelStore } from '../../stores/channelStore.js'
import { useEventStore } from '../../stores/eventStore.js'
import { MEDIAMTX_URL } from '../../constants/mediamtx.js'

const props = defineProps({ channel: Object, canEdit: { type: Boolean, default: false } })
defineEmits(['edit', 'remove'])

const channelStore = useChannelStore()
const { notifHistory } = storeToRefs(useEventStore())

// 이벤트 점등 상태(emergency=위험 / warning=경고) — channelStore.setAlertLevel이 30초 타이머로 관리
const alertLevel = computed(() => props.channel.alertLevel ?? null)

const cardStateClass = computed(() => {
  if (alertLevel.value === 'emergency') return 'alert-state'
  if (alertLevel.value === 'warning') return 'warning-state'
  return ''
})

const badgeClass = computed(() => {
  if (alertLevel.value === 'emergency') return 'badge-alert'
  if (alertLevel.value === 'warning') return 'badge-warning'
  return 'badge-ok'
})

const badgeText = computed(() => {
  if (alertLevel.value === 'emergency') return '위험'
  if (alertLevel.value === 'warning') return '경고'
  return '정상'
})

// name-strip 마지막 이벤트 표시용 (이 카드의 camera_id와 일치하는 최신 알림)
const lastEvent = computed(() => {
  const cameraId = String(props.channel.camera_id || props.channel.channelName || '')
  return notifHistory.value.find(e =>
    String(e.channel_id || e.camera_id || '') === cameraId
  ) ?? null
})

function formatEventTime(ts) {
  if (!ts) return ''
  const n = Number(ts)
  const d = isNaN(n) ? new Date(ts) : new Date(n < 1e12 ? n * 1000 : n)
  return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

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

// MediaMTX 경로는 현장 격리를 위해 site 접두사가 붙음(mtxPath). 구버전 데이터 대비 channelName 폴백.
const mtxPath = props.channel.mtxPath || props.channel.channelName
const { videoRef, status, error, connect, disconnect } = useWebRTC(
  `${MEDIAMTX_URL}/${mtxPath}/whep`
)
const { startPublish, stopPublish } = useWebRTCPublish()

function startStream() {
  const { url, sourceType } = props.channel
  if (isWebcam.value) {
    startPublish(`/webrtc/${mtxPath}/whip`, videoRef.value).catch(() => {})
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

<style scoped>
.channel-card {
  position: relative;
  height: 100%;
  border-radius: 20px;
  overflow: hidden;
  background: #1A2209;
  border: 1px solid rgba(192, 245, 61, 0.15);
  transition: border-color 0.3s ease, box-shadow 0.3s ease;
}
.channel-card:hover { border-color: rgba(192, 245, 61, 0.30); box-shadow: 0 4px 20px rgba(192, 245, 61, 0.08); }
.channel-card.alert-state  { border-color: rgba(239, 68, 68, 0.60); animation: alert-pulse 1.5s ease-in-out infinite; }
.channel-card.warning-state { border-color: rgba(251, 191, 36, 0.55); }

.video-area { position: absolute; inset: 0; }

/* 상태 배지 (LIVE / 위험 / 경고) */
.status-badge {
  position: absolute;
  top: 14px; left: 14px;
  z-index: 10;
  display: flex;
  align-items: center;
  gap: 6px;
  font-size: 11px;
  font-weight: 600;
  padding: 5px 13px;
  border-radius: 9999px;
  backdrop-filter: blur(10px);
  letter-spacing: 0.04em;
}
.status-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }

.badge-ok  { background: rgba(0,0,0,0.50); color: #C0F53D; border: 1px solid rgba(192,245,61,0.35); }
.badge-ok .status-dot { background: #C0F53D; animation: pulse 2s ease-in-out infinite; }
.badge-alert   { background: rgba(220,38,38,0.22); color: #fca5a5; border: 1px solid rgba(220,38,38,0.45); }
.badge-alert .status-dot { background: #ef4444; }
.badge-warning { background: rgba(251,191,36,0.15); color: #fde68a; border: 1px solid rgba(251,191,36,0.40); }
.badge-warning .status-dot { background: #fbbf24; }

/* 호버 액션 버튼 */
.hover-actions {
  position: absolute;
  top: 14px; right: 14px;
  z-index: 10;
  display: none;
  gap: 6px;
}
.channel-card:hover .hover-actions { display: flex; }

.hover-btn {
  padding: 6px 12px;
  border-radius: 8px;
  font-size: 12px;
  font-weight: 500;
  border: 1px solid rgba(255,255,255,0.18);
  background: rgba(0,0,0,0.65);
  color: #FAFFF3;
  cursor: pointer;
  backdrop-filter: blur(8px);
  transition: all 0.15s ease;
}
.hover-btn:hover { background: rgba(192,245,61,0.18); border-color: rgba(192,245,61,0.45); color: #C0F53D; }

/* 하단 채널명 스트립 */
.name-strip {
  position: absolute;
  bottom: 0; left: 0; right: 0;
  padding: 48px 16px 16px;
  background: linear-gradient(to top, rgba(0,0,0,0.75) 0%, transparent 100%);
  color: #FAFFF3;
  font-size: 14px;
  font-weight: 600;
  z-index: 5;
}

@keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.45; } }
@keyframes alert-pulse {
  0%, 100% { box-shadow: 0 0 0 0 rgba(239,68,68,0); }
  50%       { box-shadow: 0 0 14px 4px rgba(239,68,68,0.30); }
}
</style>
