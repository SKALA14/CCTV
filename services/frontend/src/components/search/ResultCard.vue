<template>
  <div class="flex gap-4 py-4 last:border-b-0" style="border-bottom: 1px solid var(--border);">
    <!-- 썸네일 -->
    <div
      class="w-20 h-14 flex-shrink-0 rounded-lg flex items-center justify-center text-xs overflow-hidden"
      style="background: var(--bg-elevated); color: var(--text-muted);"
    >
      <img
        v-if="event.thumbnail_url"
        :src="event.thumbnail_url"
        class="w-full h-full object-cover"
        alt=""
      />
      <span v-else>썸네일</span>
    </div>

    <!-- 정보 -->
    <div class="flex-1 min-w-0">
      <div class="flex items-center gap-2 mb-1">
        <span class="text-sm font-medium" style="color: var(--text-primary);">{{ event.channel_name }}</span>
        <span class="text-xs" style="color: var(--text-muted);">·</span>
        <span class="text-xs" style="color: var(--text-muted);">{{ formatTime(event.timestamp) }}</span>
      </div>
      <p class="text-sm line-clamp-2 leading-relaxed" style="color: var(--text-muted);">{{ event.description }}</p>
    </div>

    <!-- 배지 + 버튼 -->
    <div class="flex flex-col items-end justify-between flex-shrink-0 gap-2">
      <span class="danger-badge" :class="event.danger_level">{{ event.danger_level }}</span>
      <button
        class="px-3 py-1.5 rounded-lg text-xs transition-colors whitespace-nowrap"
        style="border: 1px solid var(--border); color: var(--text-muted);"
        @mouseover="e => { e.currentTarget.style.borderColor = 'var(--text-muted)'; e.currentTarget.style.color = 'var(--text-primary)'; }"
        @mouseleave="e => { e.currentTarget.style.borderColor = 'var(--border)'; e.currentTarget.style.color = 'var(--text-muted)'; }"
        @click="goToClip"
      >클립 재생</button>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'

const props = defineProps({ event: Object })
const router = useRouter()

function formatTime(iso) {
  return new Date(iso).toLocaleString('ko-KR', {
    month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}

function goToClip() {
  router.push(`/search/${props.event.id}`)
}
</script>
