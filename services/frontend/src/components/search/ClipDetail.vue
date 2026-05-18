<template>
  <div>
    <!-- 헤더 -->
    <div class="flex items-center gap-3 mb-5">
      <button
        class="flex items-center gap-1.5 text-sm transition-colors"
        style="color: var(--text-muted);"
        @mouseover="e => e.currentTarget.style.color = 'var(--text-primary)'"
        @mouseleave="e => e.currentTarget.style.color = 'var(--text-muted)'"
        @click="router.back()"
      >← 검색 결과로 돌아가기</button>
      <span style="color: var(--border);">|</span>
      <span class="font-semibold" style="color: var(--text-primary);">클립 상세</span>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <!-- 왼쪽: 플레이어 + 타임라인 + 미니 리스트 -->
      <div class="lg:col-span-2 space-y-4">
        <!-- 비디오 플레이어 -->
        <div class="rounded-xl overflow-hidden" style="background: var(--bg-card); border: 1px solid var(--border);">
          <!-- 비디오 영역 -->
          <div
            class="relative aspect-video bg-black cursor-pointer select-none"
            @click="togglePlay"
          >
            <video
              ref="videoEl"
              :src="event.clip_url"
              :poster="event.thumbnail_url ?? undefined"
              class="w-full h-full"
              preload="metadata"
              @timeupdate="onTimeUpdate"
              @loadedmetadata="onMetadata"
              @ended="isPlaying = false"
            ></video>

            <!-- 썸네일 폴백 -->
            <div
              v-if="!event.clip_url && !event.thumbnail_url"
              class="absolute inset-0 flex flex-col items-center justify-center gap-2"
              style="color: var(--text-subtle); pointer-events: none;"
            >
              <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor" opacity="0.3"><path d="M8 5v14l11-7z"/></svg>
              <span class="text-xs">{{ event.channel_name }} — {{ formatDateTime(event.occurred_at) }}</span>
            </div>

            <!-- 재생 버튼 오버레이 -->
            <transition name="fade">
              <div v-if="!isPlaying" class="absolute inset-0 flex items-center justify-center" style="pointer-events: none;">
                <div class="flex items-center justify-center rounded-full"
                  style="width: 64px; height: 64px; background: rgba(0,0,0,0.6); backdrop-filter: blur(2px);">
                  <svg width="26" height="26" viewBox="0 0 24 24" fill="white" style="margin-left: 3px;"><path d="M8 5v14l11-7z"/></svg>
                </div>
              </div>
            </transition>

            <div class="absolute top-3 left-3" @click.stop>
              <span class="px-2 py-1 rounded bg-[#dc2626]/80 text-xs text-white font-medium">이벤트 구간</span>
            </div>
            <div class="absolute top-3 right-3" @click.stop>
              <span class="px-2 py-1 rounded bg-black/60 text-xs text-[#8e8e93]">±10초 클립</span>
            </div>
          </div>

          <!-- 타임라인 -->
          <div class="px-4 pt-3 pb-1">
            <div
              class="relative h-1 rounded-full cursor-pointer group"
              style="background: var(--track-bg);"
              @click="seekTimeline"
            >
              <div
                class="absolute left-0 top-0 h-full rounded-full"
                style="background: var(--red); transition: width 0.1s linear;"
                :style="{ width: progressPct + '%' }"
              ></div>
              <div
                class="absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full -translate-x-1/2 shadow"
                style="background: var(--red);"
                :style="{ left: progressPct + '%' }"
              ></div>
            </div>
            <div class="flex justify-between text-xs mt-1.5" style="color: var(--text-subtle);">
              <span class="tabular-nums">{{ formatSec(currentTime) }}</span>
              <span class="font-medium" style="color: var(--red);">이벤트</span>
              <span class="tabular-nums">{{ formatSec(duration) }}</span>
            </div>
          </div>

          <!-- 컨트롤 바 -->
          <div class="flex items-center justify-between px-4 pb-3 pt-1">
            <!-- 좌측 -->
            <div class="flex items-center gap-3">
              <!-- -10초 -->
              <button class="ctrl-btn" @click="skipBy(-10)" title="-10초">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 5V1L7 6l5 5V7c3.31 0 6 2.69 6 6s-2.69 6-6 6-6-2.69-6-6H4c0 4.42 3.58 8 8 8s8-3.58 8-8-3.58-8-8-8z"/>
                  <text x="12" y="15.5" text-anchor="middle" font-size="5.5" font-weight="bold" fill="currentColor" font-family="sans-serif">10</text>
                </svg>
              </button>
              <!-- 재생/일시정지 -->
              <button class="ctrl-btn" style="width:32px;height:32px;" @click="togglePlay">
                <!-- pause -->
                <svg v-if="isPlaying" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M6 19h4V5H6v14zm8-14v14h4V5h-4z"/>
                </svg>
                <!-- play -->
                <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M8 5v14l11-7z"/>
                </svg>
              </button>
              <!-- +10초 -->
              <button class="ctrl-btn" @click="skipBy(10)" title="+10초">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M12 5V1l5 5-5 5V7c-3.31 0-6 2.69-6 6s2.69 6 6 6 6-2.69 6-6h2c0 4.42-3.58 8-8 8s-8-3.58-8-8 3.58-8 8-8z"/>
                  <text x="12" y="15.5" text-anchor="middle" font-size="5.5" font-weight="bold" fill="currentColor" font-family="sans-serif">10</text>
                </svg>
              </button>
              <!-- 음량 -->
              <button class="ctrl-btn" @click="toggleMute" :title="isMuted ? '음소거 해제' : '음소거'">
                <svg v-if="!isMuted" width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M3 9v6h4l5 5V4L7 9H3zm13.5 3c0-1.77-1.02-3.29-2.5-4.03v8.05c1.48-.73 2.5-2.25 2.5-4.02zM14 3.23v2.06c2.89.86 5 3.54 5 6.71s-2.11 5.85-5 6.71v2.06c4.01-.91 7-4.49 7-8.77s-2.99-7.86-7-8.77z"/>
                </svg>
                <svg v-else width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M16.5 12c0-1.77-1.02-3.29-2.5-4.03v2.21l2.45 2.45c.03-.2.05-.41.05-.63zm2.5 0c0 .94-.2 1.82-.54 2.64l1.51 1.51C20.63 14.91 21 13.5 21 12c0-4.28-2.99-7.86-7-8.77v2.06c2.89.86 5 3.54 5 6.71zM4.27 3L3 4.27 7.73 9H3v6h4l5 5v-6.73l4.25 4.25c-.67.52-1.42.93-2.25 1.18v2.06c1.38-.31 2.63-.95 3.69-1.81L19.73 21 21 19.73l-9-9L4.27 3zM12 4L9.91 6.09 12 8.18V4z"/>
                </svg>
              </button>
              <!-- 재생 속도 -->
              <button
                class="ctrl-btn text-xs font-medium tabular-nums"
                style="min-width: 36px; font-size: 12px;"
                @click="cycleSpeed"
                :title="'재생 속도: ' + speed + 'x'"
              >{{ speed }}x</button>
            </div>

            <!-- 우측 -->
            <div class="flex items-center gap-2">
              <!-- 전체화면 -->
              <button class="ctrl-btn" @click="toggleFullscreen" title="전체화면">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/>
                </svg>
              </button>
            </div>
          </div>
        </div>

        <!-- 미니 클립 리스트 -->
        <div v-if="relatedEvents && relatedEvents.length > 0">
          <p class="text-xs mb-2" style="color: var(--text-subtle);">
            검색 결과 {{ relatedEvents.length }}건 — 다른 클립 선택
          </p>
          <div class="rounded-xl" style="background: var(--bg-card); border: 1px solid var(--border);">
            <div
              v-for="(rel, i) in relatedEvents"
              :key="rel.id"
              class="flex items-center gap-3 px-4 py-3 cursor-pointer transition-colors"
              :style="[
                i < relatedEvents.length - 1 ? 'border-bottom: 1px solid var(--border);' : '',
                rel.id === event.id ? 'background: var(--bg-elevated);' : '',
              ].join('')"
              @mouseover="e => { if (rel.id !== event.id) e.currentTarget.style.background = 'var(--bg-elevated)' }"
              @mouseleave="e => { if (rel.id !== event.id) e.currentTarget.style.background = '' }"
              @click="goToClip(rel.id)"
            >
              <div class="w-12 h-9 rounded flex-shrink-0 flex items-center justify-center text-xs overflow-hidden"
                style="background: var(--track-bg); color: var(--text-subtle);">
                <img v-if="rel.thumbnail_url" :src="rel.thumbnail_url" class="w-full h-full object-cover" alt="" />
                <span v-else>{{ rel.channel_id || '' }}</span>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium truncate" style="color: var(--text-primary);">{{ rel.channel_name }}</p>
                <p class="text-xs truncate" style="color: var(--text-subtle);">
                  {{ formatDateTime(rel.occurred_at) }} · {{ rel.event_type }}
                </p>
              </div>
              <span class="danger-badge flex-shrink-0" :class="rel.danger_level">{{ rel.danger_level }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- 오른쪽: 메타 패널 -->
      <div class="space-y-4">
        <!-- 이벤트 정보 -->
        <div class="rounded-xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
          <h3 class="font-semibold text-sm mb-4" style="color: var(--text-primary);">이벤트 정보</h3>
          <dl class="space-y-3">
            <div class="flex justify-between">
              <dt class="text-xs" style="color: var(--text-subtle);">채널</dt>
              <dd class="text-xs text-right" style="color: var(--text-primary);">{{ event.channel_name }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-xs" style="color: var(--text-subtle);">발생 시각</dt>
              <dd class="text-xs text-right" style="color: var(--text-primary);">{{ formatDateTime(event.occurred_at) }}</dd>
            </div>
            <div class="flex justify-between">
              <dt class="text-xs" style="color: var(--text-subtle);">이벤트 유형</dt>
              <dd class="text-xs text-right" style="color: var(--text-primary);">{{ event.event_type }}</dd>
            </div>
            <div class="flex justify-between items-center">
              <dt class="text-xs" style="color: var(--text-subtle);">위험도</dt>
              <dd>
                <span class="danger-badge" :class="event.danger_level">{{ event.danger_level }}</span>
              </dd>
            </div>
            <div v-if="event.confidence != null" class="flex justify-between">
              <dt class="text-xs" style="color: var(--text-subtle);">YOLO 신뢰도</dt>
              <dd class="text-xs font-mono" style="color: var(--text-primary);">{{ event.confidence.toFixed(2) }}</dd>
            </div>
            <div v-if="event.pose_event" class="flex justify-between">
              <dt class="text-xs" style="color: var(--text-subtle);">Pose 이벤트</dt>
              <dd class="text-xs text-right" style="color: var(--text-primary);">{{ event.pose_event }}</dd>
            </div>
          </dl>
        </div>

        <!-- VLM 판단 결과 -->
        <div class="rounded-xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
          <h3 class="font-semibold text-sm mb-3" style="color: var(--text-primary);">VLM 판단 결과</h3>
          <p class="text-sm leading-relaxed mb-4" style="color: var(--text-muted);">{{ event.reason }}</p>
          <div v-if="event.vlm_confidence != null">
            <div class="flex justify-between text-xs mb-1.5" style="color: var(--text-subtle);">
              <span>신뢰도</span>
              <span class="font-mono">{{ event.vlm_confidence.toFixed(2) }}</span>
            </div>
            <div class="h-1.5 rounded-full overflow-hidden" style="background: var(--track-bg);">
              <div
                class="h-full rounded-full transition-all"
                :style="{
                  width: `${event.vlm_confidence * 100}%`,
                  background: event.vlm_confidence >= 0.7 ? 'var(--red)' : 'var(--orange)',
                }"
              ></div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  event: Object,
  relatedEvents: { type: Array, default: () => [] },
})

const router = useRouter()
const videoEl = ref(null)
const isPlaying = ref(false)
const isMuted = ref(false)
const currentTime = ref(0)
const duration = ref(0)
const speed = ref(1)
const SPEEDS = [1, 1.25, 1.5, 2, 0.5]

const progressPct = computed(() => duration.value
  ? (currentTime.value / duration.value) * 100
  : 0)

function onTimeUpdate() { currentTime.value = videoEl.value?.currentTime ?? 0 }
function onMetadata() { duration.value = videoEl.value?.duration ?? 0 }

function togglePlay() {
  if (!videoEl.value) return
  if (isPlaying.value) { videoEl.value.pause(); isPlaying.value = false }
  else { isPlaying.value = true; videoEl.value.play().catch(() => { isPlaying.value = false }) }
}

function skipBy(sec) {
  if (!videoEl.value) return
  videoEl.value.currentTime = Math.max(0, Math.min(videoEl.value.currentTime + sec, duration.value))
}

function toggleMute() {
  if (!videoEl.value) return
  isMuted.value = !isMuted.value
  videoEl.value.muted = isMuted.value
}

function cycleSpeed() {
  const idx = SPEEDS.indexOf(speed.value)
  speed.value = SPEEDS[(idx + 1) % SPEEDS.length]
  if (videoEl.value) videoEl.value.playbackRate = speed.value
}

function toggleFullscreen() { videoEl.value?.requestFullscreen?.() }

function seekTimeline(e) {
  if (!videoEl.value) return
  const rect = e.currentTarget.getBoundingClientRect()
  videoEl.value.currentTime = ((e.clientX - rect.left) / rect.width) * duration.value
}

function formatSec(s) {
  const m = Math.floor((s || 0) / 60)
  const sec = Math.floor((s || 0) % 60)
  return `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`
}

function formatDateTime(iso) {
  return new Date(iso).toLocaleString('ko-KR', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit', second: '2-digit',
  })
}

function goToClip(id) { router.push(`/search/${id}`) }
</script>

<style scoped>
.fade-enter-active, .fade-leave-active { transition: opacity 0.2s ease; }
.fade-enter-from, .fade-leave-to { opacity: 0; }

.ctrl-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-muted);
  border-radius: 6px;
  padding: 4px;
  transition: color 0.15s, background 0.15s;
}
.ctrl-btn:hover {
  color: var(--text-primary);
  background: var(--bg-elevated);
}
</style>
