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
          <!-- 비디오 영역 (항상 다크) -->
          <div class="relative aspect-video bg-black">
            <video
              ref="videoEl"
              :src="event.clip_url"
              class="w-full h-full"
              preload="metadata"
              @timeupdate="onTimeUpdate"
              @loadedmetadata="onMetadata"
            ></video>

            <div class="absolute top-3 left-3">
              <span class="px-2 py-1 rounded bg-[#dc2626]/80 text-xs text-white font-medium">이벤트 구간</span>
            </div>
            <div class="absolute top-3 right-3">
              <span class="px-2 py-1 rounded bg-black/60 text-xs text-[#8e8e93]">±10초 클립</span>
            </div>

            <div v-if="!event.clip_url" class="absolute inset-0 flex flex-col items-center justify-center gap-2 text-[#48484a]">
              <svg width="48" height="48" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8 5v14l11-7z"/>
              </svg>
              <span class="text-sm">{{ event.channel_name }} — {{ formatDateTime(event.timestamp) }}</span>
            </div>
          </div>

          <!-- 타임라인 -->
          <div class="px-4 pt-3 pb-2">
            <div class="relative h-1.5 rounded-full mb-2 cursor-pointer" style="background: var(--track-bg);" @click="seekTimeline">
              <div
                class="absolute left-0 top-0 h-full bg-blue-500 rounded-full transition-all"
                :style="{ width: progressPct + '%' }"
              ></div>
              <div
                class="absolute top-1/2 -translate-y-1/2 w-2.5 h-2.5 rounded-full -translate-x-1/2"
                style="background: var(--red); left: 50%;"
              ></div>
            </div>
            <div class="flex justify-between text-xs" style="color: var(--text-subtle);">
              <span>-10s</span>
              <span class="font-medium" style="color: var(--red);">이벤트</span>
              <span>+10s</span>
            </div>
          </div>

          <!-- 컨트롤 바 -->
          <div class="flex items-center gap-3 px-4 pb-3">
            <button class="text-xs transition-colors" style="color: var(--text-muted);" @click="seekToStart">처음</button>
            <button class="text-xs transition-colors" style="color: var(--text-muted);" @click="togglePlay">
              {{ isPlaying ? '일시정지' : '재생' }}
            </button>
            <span class="text-xs tabular-nums ml-1" style="color: var(--text-subtle);">
              {{ formatSec(currentTime) }} / {{ formatSec(duration) }}
            </span>
            <div class="flex-1"></div>
            <button
              class="text-xs rounded px-2 py-0.5 transition-colors"
              style="color: var(--text-muted); border: 1px solid var(--border);"
              @click="cycleSpeed"
            >{{ speed }}x</button>
            <button
              class="text-xs rounded px-2 py-0.5 transition-colors"
              style="color: var(--text-muted); border: 1px solid var(--border);"
              @click="toggleFullscreen"
            >전체화면</button>
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
                <span v-else>{{ rel.camera_id || '' }}</span>
              </div>
              <div class="flex-1 min-w-0">
                <p class="text-sm font-medium truncate" style="color: var(--text-primary);">{{ rel.channel_name }}</p>
                <p class="text-xs truncate" style="color: var(--text-subtle);">
                  {{ formatDateTime(rel.timestamp) }} · {{ rel.event_type }}
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
              <dd class="text-xs text-right" style="color: var(--text-primary);">{{ formatDateTime(event.timestamp) }}</dd>
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
          <p class="text-sm leading-relaxed mb-4" style="color: var(--text-muted);">{{ event.description }}</p>
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
const currentTime = ref(0)
const duration = ref(20)
const speed = ref(1)
const SPEEDS = [1, 1.5, 2, 0.5]

const progressPct = computed(() => duration.value
  ? (currentTime.value / duration.value) * 100
  : 0)

function onTimeUpdate() { currentTime.value = videoEl.value?.currentTime ?? 0 }
function onMetadata() { duration.value = videoEl.value?.duration ?? 20 }

function togglePlay() {
  if (!videoEl.value) return
  if (isPlaying.value) { videoEl.value.pause(); isPlaying.value = false }
  else { videoEl.value.play(); isPlaying.value = true }
}

function seekToStart() {
  if (!videoEl.value) return
  videoEl.value.currentTime = 0
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
  const m = Math.floor(s / 60)
  const sec = Math.floor(s % 60)
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
