<template>
  <div class="p-4 max-w-3xl mx-auto">
    <h1 class="text-lg font-bold mb-1" style="color: var(--text-primary);">즐겨찾기</h1>
    <p class="text-xs mb-4" style="color: var(--text-subtle);">후속 조치가 필요한 이벤트를 모아둔 곳입니다.</p>

    <div v-if="store.items.length === 0" class="text-center py-16 text-sm" style="color: var(--text-subtle);">
      저장된 이벤트가 없습니다. 이벤트 상세에서 ☆ 를 눌러 저장하세요.
    </div>
    <div v-else class="flex flex-col gap-2.5">
      <div v-for="b in store.items" :key="b.event_id"
        class="rounded-xl p-3 flex items-center gap-3 cursor-pointer transition-colors"
        style="background: var(--bg-card); border: 1px solid var(--border);"
        @click="open(b)">
        <div class="w-14 h-14 rounded-lg flex-shrink-0 overflow-hidden" style="background: var(--bg-elevated);">
          <img v-if="b.thumbnail_url" :src="b.thumbnail_url" class="w-full h-full object-cover" />
        </div>
        <div class="flex-1 min-w-0">
          <div class="flex items-center gap-2 mb-0.5">
            <span class="danger-badge" :class="b.danger_level">{{ b.danger_level }}</span>
            <span class="text-xs" style="color: var(--text-muted);">{{ b.camera_name }}</span>
          </div>
          <p class="text-sm truncate" style="color: var(--text-primary);">{{ b.description || '—' }}</p>
          <p class="text-[11px] mt-0.5" style="color: var(--text-subtle);">{{ fmt(b.occurred_at) }}</p>
        </div>
        <button class="text-xs px-2 py-1 rounded flex-shrink-0" style="color: var(--red);"
          @click.stop="store.remove(b.event_id)">삭제</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { useRouter } from 'vue-router'
import { useBookmarkStore } from '../stores/bookmarkStore.js'

const store = useBookmarkStore()
const router = useRouter()

function open(b) { router.push(`/search/${b.event_id}`) }
function fmt(iso) {
  try { return new Date(iso).toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' }) }
  catch { return iso }
}
</script>
