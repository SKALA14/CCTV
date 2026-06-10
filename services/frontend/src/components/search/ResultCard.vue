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
      <div class="flex items-center gap-2 mb-1 flex-wrap">
        <span
          v-if="isSuperadmin && event.site_name"
          class="text-[10px] px-1.5 py-0.5 rounded-full font-medium"
          style="background: var(--bg-elevated); color: var(--text-muted); border: 1px solid var(--border);"
        >{{ event.site_name }}</span>
        <span class="text-sm font-medium" style="color: var(--text-primary);">{{ event.channel_name }}</span>
        <span class="text-xs" style="color: var(--text-muted);">·</span>
        <span class="text-xs" style="color: var(--text-muted);">{{ timeRangeLabel }}</span>
        <span
          v-if="isIncident"
          class="text-[10px] px-1.5 py-0.5 rounded-full font-medium tabular-nums"
          style="background: var(--bg-elevated); color: var(--text-muted);"
          :title="`이 사건은 ${event.incident_count}건의 감지로 ${durationLabel} 동안 지속됨`"
        >×{{ event.incident_count }} · {{ durationLabel }}</span>
      </div>
      <p class="text-sm line-clamp-2 leading-relaxed" style="color: var(--text-muted);">{{ event.reason }}</p>
    </div>

    <!-- 배지 + 버튼 -->
    <div class="flex flex-col items-end justify-between flex-shrink-0 gap-2">
      <div class="flex items-center gap-1.5">
        <span
          v-if="event.similarity != null"
          class="text-xs tabular-nums"
          style="color: var(--text-muted);"
        >{{ Math.round(event.similarity * 100) }}% 일치</span>
        <span class="danger-badge" :class="event.danger_level">{{ event.danger_level }}</span>
      </div>
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
import { computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../../stores/authStore.js'

const props = defineProps({ event: Object })
const router = useRouter()
const authStore = useAuthStore()
const isSuperadmin = computed(() => authStore.isSuperadmin)

const isIncident = computed(() => (props.event.incident_count ?? 1) > 1)

const timeRangeLabel = computed(() => {
  const start = formatTime(props.event.occurred_at)
  if (!isIncident.value || !props.event.incident_last_at) return start
  return `${start} ~ ${formatTime(props.event.incident_last_at)}`
})

const durationLabel = computed(() => {
  if (!props.event.incident_last_at) return ''
  const start = new Date(props.event.occurred_at).getTime()
  const end = new Date(props.event.incident_last_at).getTime()
  const sec = Math.max(0, Math.round((end - start) / 1000))
  if (sec < 60) return `${sec}초`
  const min = Math.floor(sec / 60)
  const rem = sec % 60
  return rem === 0 ? `${min}분` : `${min}분${rem}초`
})

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
