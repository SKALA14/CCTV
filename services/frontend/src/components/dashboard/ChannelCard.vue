<template>
  <div class="channel-card" :class="{ 'alert-state': isAlert }">
    <div class="status-badge" :class="isAlert ? 'badge-alert' : 'badge-ok'">
      <span class="status-dot"></span>
      {{ isAlert ? channel.event_type : '정상' }}
    </div>

    <div class="video-area">
      <video
        ref="videoEl"
        autoplay
        muted
        playsinline
        style="width:100%; height:100%; object-fit:cover; border-radius:inherit;"
      />
      <div
        v-if="webcamError"
        class="flex flex-col items-center justify-center gap-1"
        style="position:absolute; inset:0; background:rgba(0,0,0,0.7);"
      >
        <span class="text-2xl">🚫</span>
        <span class="text-xs text-center" style="color:#fff;">웹캠 접근 실패<br>브라우저 권한을 확인해주세요</span>
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
import Hls from 'hls.js'

const props = defineProps({ channel: Object })
defineEmits(['edit', 'remove'])

const isAlert = computed(() => props.channel.status === 'alert')
const videoEl = ref(null)
const webcamError = ref(false)

let hls    = null
let stream = null

function attachSource(url, cameraId) {
  if (/\.m3u8(\?|$)/i.test(url)) {
    attachHls(url)
  } else if (/\.(mp4|webm|ogg)(\?|$)/i.test(url)) {
    videoEl.value.src = url
  } else {
    attachHls(`/hls/${cameraId}/index.m3u8`)
  }
}

function attachHls(src) {
  if (Hls.isSupported()) {
    hls = new Hls()
    hls.on(Hls.Events.ERROR, (_, data) => {
      if (!data.fatal) return
      if (data.type === Hls.ErrorTypes.NETWORK_ERROR) hls.startLoad()
      else if (data.type === Hls.ErrorTypes.MEDIA_ERROR) hls.recoverMediaError()
      else destroyHls()
    })
    hls.attachMedia(videoEl.value)
    hls.on(Hls.Events.MEDIA_ATTACHED, () => hls.loadSource(src))
  } else {
    videoEl.value.src = src
  }
}

function destroyHls() {
  hls?.destroy()
  hls = null
}

onMounted(async () => {
  if (props.channel.url === 'webcam') {
    try {
      stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      videoEl.value.srcObject = stream
    } catch (e) {
      webcamError.value = true
    }
  } else {
    attachSource(props.channel.url, props.channel.camera_id)
  }
})

watch(() => props.channel.url, (newUrl) => {
  destroyHls()
  stream?.getTracks().forEach(t => t.stop())
  stream = null
  webcamError.value = false
  videoEl.value.src = ''

  if (newUrl === 'webcam') {
    navigator.mediaDevices.getUserMedia({ video: true, audio: false })
      .then(s => { stream = s; videoEl.value.srcObject = s })
      .catch(() => { webcamError.value = true })
  } else {
    videoEl.value.srcObject = null
    attachSource(newUrl, props.channel.camera_id)
  }
})

onUnmounted(() => {
  destroyHls()
  stream?.getTracks().forEach(t => t.stop())
})
</script>
