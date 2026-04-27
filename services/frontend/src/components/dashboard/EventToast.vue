<template>
  <transition name="banner">
    <div v-if="latest" class="banner-toast">
      🔴 &nbsp;이벤트 감지 — {{ latest.channel_name }} / {{ latest.event_type }} / {{ formatTime(latest.created_at) }}
    </div>
  </transition>
</template>

<script setup>
import { computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useEventStore } from '../../stores/eventStore.js'

const { toastQueue } = storeToRefs(useEventStore())
const latest = computed(() => toastQueue.value[0] ?? null)

function formatTime(iso) {
  return new Date(iso).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit' })
}
</script>
