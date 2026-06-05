<template>
  <aside
    class="flex flex-col flex-shrink-0 overflow-hidden"
    style="width: 236px; border-left: 1px solid var(--border); background: var(--bg-card);"
  >
    <div
      class="flex items-center justify-between px-4 py-2.5 flex-shrink-0"
      style="border-bottom: 1px solid var(--border);"
    >
      <span class="text-[11px] font-semibold tracking-wider uppercase" style="color: var(--text-muted);">이벤트</span>
      <span
        v-if="events.length > 0"
        class="text-[10px] font-semibold px-1.5 py-0.5 rounded"
        style="background: rgba(220,38,38,0.15); color: #dc2626;"
      >{{ events.length }}</span>
    </div>

    <div v-if="events.length === 0" class="flex-1 flex items-center justify-center">
      <span class="text-xs" style="color: var(--text-subtle);">감지된 이벤트 없음</span>
    </div>

    <div v-else class="flex-1 overflow-y-auto">
      <div
        v-for="(e, i) in events"
        :key="i"
        class="px-3 py-2.5"
        style="border-bottom: 1px solid var(--border);"
      >
        <div class="flex items-start gap-2">
          <span
            class="mt-[3px] flex-shrink-0 w-1.5 h-1.5 rounded-full"
            :style="e.pipeline === 'emergency' ? 'background:#dc2626' : 'background:#f59e0b'"
          ></span>
          <div class="flex-1 min-w-0">
            <div class="flex items-center justify-between gap-1">
              <span class="text-xs font-medium truncate" style="color: var(--text-primary);">
                {{ resolveChannelName(e) }}
              </span>
              <span class="text-[10px] flex-shrink-0" style="color: var(--text-subtle);">
                {{ formatTime(e.timestamp) }}
              </span>
            </div>
            <div class="mt-1 flex items-center gap-1.5">
              <span
                class="text-[10px] px-1.5 py-px rounded font-medium"
                :class="dangerClass(e.danger_level)"
              >{{ e.event_type }}</span>
              <span
                v-if="e.pipeline === 'emergency'"
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

const { liveEvents } = storeToRefs(useEventStore())
const { slots } = useChannels()

const events = computed(() =>
  liveEvents.value
    .filter(e => e.danger_level && e.danger_level !== 'none' && e.event_type !== 'normal')
    .slice(0, 30)
)

function resolveChannelName(e) {
  const cameraId = String(e.channel_id || e.camera_id || '')
  const ch = slots.value.find(c => c && String(c.camera_id || c.channelName || '') === cameraId)
  return ch?.name || e.channel_name || cameraId || '알 수 없음'
}

function formatTime(ts) {
  if (!ts) return ''
  const n = Number(ts)
  const d = isNaN(n) ? new Date(ts) : new Date(n * (String(ts).length <= 10 ? 1000 : 1))
  return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function dangerClass(level) {
  if (level === 'high') return 'bg-red-900/30 text-red-400'
  if (level === 'medium') return 'bg-yellow-900/30 text-yellow-400'
  return 'bg-green-900/30 text-green-400'
}
</script>
