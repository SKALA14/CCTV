<!-- 알림 히스토리 패널 (우측) -->
<template>
  <aside
    class="flex flex-col overflow-hidden absolute right-0 top-0 bottom-0"
    style="width: 236px; border-left: 1px solid var(--border); background: var(--bg-card); z-index: 10; box-shadow: -4px 0 20px rgba(0,0,0,0.35);"
  >
    <div
      class="flex items-center justify-between px-4 py-2.5 flex-shrink-0"
      style="border-bottom: 1px solid var(--border);"
    >
      <span class="text-[11px] font-semibold tracking-wider uppercase" style="color: var(--text-muted);">알림 히스토리</span>
      <button
        v-if="history.length > 0"
        class="text-[10px] px-1.5 py-0.5 rounded transition-colors"
        style="color: var(--text-subtle);"
        @click="store.clearHistory()"
      >지우기</button>
    </div>

    <div v-if="history.length === 0" class="flex-1 flex items-center justify-center">
      <span class="text-xs" style="color: var(--text-subtle);">알림 없음</span>
    </div>

    <div v-else class="flex-1 overflow-y-auto">
      <div
        v-for="n in history"
        :key="n._notifId"
        class="px-3 py-2.5"
        style="border-bottom: 1px solid var(--border);"
      >
        <div class="flex items-start gap-2">
          <span
            class="mt-[3px] flex-shrink-0 w-1.5 h-1.5 rounded-full"
            :style="n.pipeline === 'emergency' ? 'background:#dc2626' : 'background:#f59e0b'"
          ></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between gap-1">
              <span class="text-xs font-medium truncate" style="color: var(--text-primary);">
                {{ resolveChannelName(n) }}
              </span>
              <span class="text-[10px] flex-shrink-0" style="color: var(--text-subtle);">
                {{ formatTime(n.timestamp) }}
              </span>
            </div>
            <div class="mt-1 flex items-center gap-1.5">
              <span
                class="text-[10px] px-1.5 py-px rounded font-medium"
                :class="dangerClass(n.danger_level)"
              >{{ n.event_type }}</span>
              <span
                v-if="n.pipeline === 'emergency'"
                class="text-[9px] px-1 py-px rounded font-semibold tracking-wide"
                style="background: rgba(220,38,38,0.12); color: #dc2626;"
              >EMG</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  </aside>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useEventStore } from '../../stores/eventStore.js'
import { useChannels } from '../../composables/useChannels.js'

const store = useEventStore()
const { notifHistory } = storeToRefs(store)
const { slots } = useChannels()

const history = computed(() => notifHistory.value)

function resolveChannelName(n) {
  const cameraId = String(n.channel_id || n.camera_id || '')
  const ch = slots.value.find(c => c && String(c.camera_id || c.channelName || '') === cameraId)
  return ch?.name || n.channel_name || cameraId || '알 수 없음'
}

function formatTime(ts) {
  if (!ts) return ''
  const n = Number(ts)
  const d = isNaN(n) ? new Date(ts) : new Date(n < 1e12 ? n * 1000 : n)
  return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function dangerClass(level) {
  if (level === 'critical') return 'bg-red-900/30 text-red-400'
  if (level === 'high')     return 'bg-orange-900/30 text-orange-400'
  if (level === 'low')      return 'bg-yellow-900/30 text-yellow-400'
  return 'bg-green-900/30 text-green-400'   // none
}
</script>
