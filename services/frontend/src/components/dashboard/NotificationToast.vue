<!-- 실시간 알림 토스트 (우하단) -->
<template>
  <div
    class="fixed bottom-4 right-4 z-50 flex flex-col gap-2"
    style="width: 320px; pointer-events: none;"
  >
    <transition-group name="notif">
      <div
        v-for="n in notifications"
        :key="n._notifId"
        class="notif-card"
        :class="n.pipeline === 'emergency' ? 'notif-emergency' : 'notif-general'"
        style="pointer-events: auto;"
      >
        <!-- Header -->
        <div class="notif-header">
          <div class="flex items-center gap-1.5 min-w-0">
            <span
              class="flex-shrink-0 w-1.5 h-1.5 rounded-full"
              :style="n.pipeline === 'emergency' ? 'background:#dc2626' : 'background:#22c55e'"
            ></span>
            <span class="text-sm font-semibold truncate" style="color: var(--text-primary);">
              {{ resolveChannelName(n) }}
            </span>
          </div>
          <div class="flex items-center gap-2 flex-shrink-0">
            <span class="notif-badge" :class="n.pipeline === 'emergency' ? 'badge-emg' : 'badge-vlm'">
              {{ n.pipeline === 'emergency' ? 'EMERGENCY' : 'VLM' }}
            </span>
            <button class="notif-close-btn" @click="store.dismissNotification(n._notifId)">✕</button>
          </div>
        </div>

        <!-- Body -->
        <div class="px-3 pb-2">
          <p class="text-sm leading-relaxed notif-desc">
            {{ resolveMessage(n) }}
          </p>
        </div>

        <!-- Footer -->
        <div class="flex items-center justify-between px-3 pb-2.5">
          <span class="danger-badge" :class="n.danger_level">
            {{ (n.danger_level || '').toUpperCase() }}
          </span>
          <span class="text-xs" style="color: var(--text-subtle);">{{ formatTime(n.timestamp) }}</span>
        </div>

        <!-- Timer bar -->
        <div style="height: 2px; background: var(--border);">
          <div
            class="notif-timer-fill"
            :class="n.pipeline === 'emergency' ? 'timer-emg' : 'timer-vlm'"
            :style="{ animationDuration: `${NOTIF_DURATION}ms` }"
          ></div>
        </div>
      </div>
    </transition-group>
  </div>
</template>

<script setup>
import { storeToRefs } from 'pinia'
import { useEventStore, NOTIF_DURATION } from '../../stores/eventStore.js'
import { useChannels } from '../../composables/useChannels.js'

const store = useEventStore()
const { notifications } = storeToRefs(store)
const { slots } = useChannels()

function resolveChannelName(notif) {
  const cameraId = String(notif.channel_id || notif.camera_id || '')
  const ch = slots.value.find(c => (
    String(c.camera_id || c.channelName || '') === cameraId
  ))
  return ch?.name || notif.channel_name || cameraId || '알 수 없음'
}

function formatTime(ts) {
  if (!ts) return ''
  const n = Number(ts)
  const d = isNaN(n) ? new Date(ts) : new Date(n < 1e12 ? n * 1000 : n)
  return d.toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

function resolveMessage(notif) {
  if (notif.pipeline === 'emergency') {
    const eventType = String(notif.event_type || '').toLowerCase()
    if (eventType === 'fallen') return '작업자 낙상 감지'
    if (eventType === 'fire' || eventType === 'smoke') return '화재 위험 감지'
  }
  return notif.reason || notif.description || '이상 상황이 감지되었습니다.'
}
</script>

<style scoped>
.notif-card {
  border-radius: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-left-width: 3px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.35);
  overflow: hidden;
}

.notif-emergency { border-left-color: #dc2626; }
.notif-general   { border-left-color: #f59e0b; }

.notif-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 10px 12px 8px;
  gap: 8px;
}

.notif-badge {
  font-size: 9px;
  font-weight: 700;
  letter-spacing: 0.06em;
  padding: 2px 6px;
  border-radius: 4px;
}

.badge-emg { background: rgba(220,38,38,0.15); color: #dc2626; }
.badge-vlm { background: rgba(245,158,11,0.15); color: #f59e0b; }

.notif-close-btn {
  width: 18px;
  height: 18px;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 11px;
  color: var(--text-subtle);
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 3px;
  transition: color 0.12s;
}
.notif-close-btn:hover { color: var(--text-primary); }

.notif-desc {
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
  color: var(--text-muted);
}

.notif-timer-fill {
  height: 100%;
  animation: timer-shrink linear forwards;
}

.timer-emg { background: #dc2626; }
.timer-vlm { background: #f59e0b; }

@keyframes timer-shrink {
  from { width: 100%; }
  to   { width: 0%; }
}

.notif-enter-active { transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1); }
.notif-leave-active { transition: all 0.18s ease; }
.notif-enter-from   { opacity: 0; transform: translateX(110%); }
.notif-leave-to     { opacity: 0; transform: translateX(110%); }
.notif-move         { transition: transform 0.2s ease; }
</style>
