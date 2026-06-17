<!-- 클립 상세 — 스냅샷·설명·연관 이벤트 -->
<template>
  <div>
    <!-- 헤더 -->
    <div class="flex items-center gap-3 mb-5">
      <button
        class="flex items-center gap-1.5 text-sm transition-colors"
        style="color: var(--text-muted);"
        @mouseover="e => e.currentTarget.style.color = 'var(--text-primary)'"
        @mouseleave="e => e.currentTarget.style.color = 'var(--text-muted)'"
        @click="router.push('/search')"
      >← 검색 결과로 돌아가기</button>
      <span style="color: var(--border);">|</span>
      <span class="font-semibold" style="color: var(--text-primary);">클립 상세</span>
    </div>

    <div class="grid grid-cols-1 lg:grid-cols-3 gap-5">
      <!-- 왼쪽: 플레이어 + 타임라인 + 미니 리스트 -->
      <div class="lg:col-span-2 space-y-4">
        <!-- 스냅샷 갤러리 -->
        <div class="rounded-xl overflow-hidden" style="background: var(--bg-card); border: 1px solid var(--border);">
          <!-- 이미지 영역 -->
          <div class="relative aspect-video bg-black select-none">
            <img
              v-if="currentSnapshot"
              :src="currentSnapshot"
              class="w-full h-full object-contain"
              :alt="`snapshot ${currentIndex + 1}`"
            />
            <div
              v-else
              class="absolute inset-0 flex flex-col items-center justify-center gap-2"
              style="color: var(--text-subtle);"
            >
              <svg width="40" height="40" viewBox="0 0 24 24" fill="currentColor" opacity="0.3">
                <path d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c1.1 0 2-.9 2-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z"/>
              </svg>
              <span class="text-xs">스냅샷이 없습니다</span>
            </div>

            <div class="absolute top-3 left-3">
              <span class="px-2 py-1 rounded bg-[#dc2626]/80 text-xs text-white font-medium">이벤트 스냅샷</span>
            </div>
            <div v-if="snapshots.length > 0" class="absolute top-3 right-3">
              <span class="px-2 py-1 rounded bg-black/60 text-xs text-[#8e8e93]">
                {{ currentIndex + 1 }} / {{ snapshots.length }}
              </span>
            </div>
          </div>

          <!-- 네비게이션 -->
          <div v-if="snapshots.length > 1" class="flex items-center justify-between px-4 py-3 gap-3">
            <button class="ctrl-btn" :disabled="currentIndex === 0" @click="prev" title="이전">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z"/>
              </svg>
            </button>

            <!-- 도트 인디케이터 -->
            <div class="flex items-center gap-2">
              <button
                v-for="(_, i) in snapshots"
                :key="i"
                class="rounded-full transition-all"
                :style="{
                  width: i === currentIndex ? '20px' : '8px',
                  height: '8px',
                  background: i === currentIndex ? 'var(--red)' : 'var(--track-bg)',
                }"
                @click="currentIndex = i"
              />
            </div>

            <button class="ctrl-btn" :disabled="currentIndex === snapshots.length - 1" @click="next" title="다음">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="currentColor">
                <path d="M8.59 16.59L10 18l6-6-6-6-1.41 1.41L13.17 12z"/>
              </svg>
            </button>
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
            <div v-if="isIncident" class="flex justify-between">
              <dt class="text-xs" style="color: var(--text-subtle);">지속 시간</dt>
              <dd class="text-xs text-right" style="color: var(--text-primary);">
                {{ durationLabel }}<span v-if="event.incident_count" class="ml-1" style="color: var(--text-muted);">(×{{ event.incident_count }})</span>
              </dd>
            </div>
            <div v-if="isIncident" class="flex justify-between">
              <dt class="text-xs" style="color: var(--text-subtle);">종료 시각</dt>
              <dd class="text-xs text-right" style="color: var(--text-primary);">{{ formatDateTime(event.incident_last_at) }}</dd>
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
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'

const props = defineProps({
  event: Object,
  relatedEvents: { type: Array, default: () => [] },
})

const router = useRouter()
const currentIndex = ref(0)

const snapshots = computed(() => {
  if (props.event?.snapshot_urls?.length) return props.event.snapshot_urls
  if (props.event?.thumbnail_url) return [props.event.thumbnail_url]
  return []
})

const isIncident = computed(() => (props.event?.incident_count ?? 1) > 1 && props.event?.incident_last_at)

const durationLabel = computed(() => {
  if (!isIncident.value) return ''
  const start = new Date(props.event.occurred_at).getTime()
  const end = new Date(props.event.incident_last_at).getTime()
  const sec = Math.max(0, Math.round((end - start) / 1000))
  if (sec < 60) return `${sec}초`
  const min = Math.floor(sec / 60)
  const rem = sec % 60
  return rem === 0 ? `${min}분` : `${min}분${rem}초`
})

const currentSnapshot = computed(() => snapshots.value[currentIndex.value] ?? null)

watch(() => props.event?.id, () => { currentIndex.value = 0 })

function prev() { if (currentIndex.value > 0) currentIndex.value-- }
function next() { if (currentIndex.value < snapshots.value.length - 1) currentIndex.value++ }

function onKeyDown(e) {
  if (e.key === 'ArrowLeft') prev()
  else if (e.key === 'ArrowRight') next()
}
onMounted(() => window.addEventListener('keydown', onKeyDown))
onUnmounted(() => window.removeEventListener('keydown', onKeyDown))

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
.ctrl-btn:hover:not(:disabled) {
  color: var(--text-primary);
  background: var(--bg-elevated);
}
.ctrl-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}
</style>
