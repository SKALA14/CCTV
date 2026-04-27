<template>
  <div>
    <div v-if="loading" class="flex justify-center py-12">
      <div class="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
    <div v-else-if="error" class="text-red-400 text-center py-8">{{ error }}</div>
    <div v-else-if="events.length === 0" class="text-center py-16 text-sm" style="color: var(--text-muted);">
      검색 결과가 없습니다.
    </div>
    <div v-else>
      <p class="text-xs mb-1" style="color: var(--text-muted);">검색 결과 {{ events.length }}건</p>
      <div class="rounded-xl px-4" style="background: var(--bg-card); border: 1px solid var(--border);">
        <ResultCard v-for="event in events" :key="event.id" :event="event" />
      </div>
    </div>
  </div>
</template>

<script setup>
import ResultCard from './ResultCard.vue'

defineProps({
  events: { type: Array, default: () => [] },
  loading: Boolean,
  error: String,
})
</script>
