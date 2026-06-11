<template>
  <div class="p-4 max-w-3xl mx-auto">
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-lg font-bold" style="color: var(--text-primary);">실시간 이벤트</h1>
      <span class="flex items-center gap-1.5 text-xs px-2.5 py-1 rounded-full"
            style="background: var(--bg-elevated); color: var(--text-muted);">
        <span class="w-1.5 h-1.5 rounded-full animate-pulse" style="background: #22c55e;"></span>
        LIVE · {{ events.length }}건
      </span>
    </div>

    <div v-if="loading" class="flex justify-center py-12">
      <div class="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
    <div v-else-if="events.length === 0" class="text-center py-20 text-sm" style="color: var(--text-subtle);">
      아직 감지된 이벤트가 없습니다 — 시스템이 정상 감시 중입니다 🟢
    </div>
    <div v-else class="flex flex-col gap-2.5">
      <ResultCard v-for="e in events" :key="e.id" :event="e" />
    </div>
  </div>
</template>

<script setup>
import { ref, watch, onMounted, onUnmounted } from 'vue'
import { fetchEvents } from '../api/events.js'
import { useEventStore } from '../stores/eventStore.js'
import ResultCard from '../components/search/ResultCard.vue'

const events = ref([])
const loading = ref(true)
const eventStore = useEventStore()

async function load() {
  try {
    const res = await fetchEvents({ limit: 50 })
    events.value = Array.isArray(res) ? res : (res.events || [])
  } catch { /* 무시 — 다음 폴링에서 재시도 */ } finally {
    loading.value = false
  }
}

// WebSocket으로 새 이벤트가 오면 즉시 갱신 (라이브 피드)
watch(() => eventStore.notifHistory.length, load)

let timer
onMounted(() => { load(); timer = setInterval(load, 20000) })   // 폴백 폴링
onUnmounted(() => clearInterval(timer))
</script>
