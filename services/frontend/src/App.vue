<template>
  <div class="flex h-full">
    <!-- 좌측 사이드바 -->
    <aside
      class="flex flex-col items-center w-16 border-r flex-shrink-0 py-3"
      style="background: var(--bg-card); border-color: var(--border);"
    >
      <!-- 앱 로고 -->
      <div class="mb-5 flex flex-col items-center gap-0.5">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#3b82f6" stroke-width="1.8">
          <path d="M15 10l4.553-2.277A1 1 0 0121 8.618v6.764a1 1 0 01-1.447.894L15 14"/>
          <rect x="2" y="6" width="13" height="12" rx="2"/>
        </svg>
        <span class="text-[9px] font-semibold tracking-widest" style="color: var(--text-muted);">CCTV</span>
      </div>

      <!-- 네비게이션 -->
      <AppNav class="w-full" />

      <!-- 채널 추가 버튼 (대시보드에서만) -->
      <div v-if="isDashboard" class="mt-2 px-2 w-full">
        <div class="mb-2" style="border-top: 1px solid var(--border);"></div>
        <button
          :disabled="isMaxChannels"
          class="flex flex-col items-center gap-1 w-full py-2.5 rounded-xl transition-all"
          :class="isMaxChannels
            ? 'bg-[#2c2c2e] text-[#48484a] cursor-not-allowed'
            : 'bg-blue-600 text-white hover:bg-blue-500 shadow-lg shadow-blue-900/40'"
          @click="triggerAddModal"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="12" y1="5" x2="12" y2="19" stroke-linecap="round"/>
            <line x1="5" y1="12" x2="19" y2="12" stroke-linecap="round"/>
          </svg>
          <span class="text-[9px] font-semibold">채널추가</span>
        </button>
      </div>

      <div class="flex-1"></div>

      <!-- 테마 토글 -->
      <div class="px-2 w-full">
        <div class="mb-2" style="border-top: 1px solid var(--border);"></div>
        <div
          class="flex rounded-xl overflow-hidden text-[9px] font-semibold"
          style="border: 1px solid var(--border);"
        >
          <button
            class="flex-1 flex flex-col items-center gap-1 py-2 transition-colors"
            :style="isDark
              ? 'background: var(--bg-elevated); color: var(--text-primary);'
              : 'background: transparent; color: var(--text-muted);'"
            @click="isDark || toggle()"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
            </svg>
            <span>Dark</span>
          </button>
          <button
            class="flex-1 flex flex-col items-center gap-1 py-2 transition-colors"
            :style="!isDark
              ? 'background: var(--bg-elevated); color: var(--text-primary);'
              : 'background: transparent; color: var(--text-muted);'"
            @click="isDark && toggle()"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <circle cx="12" cy="12" r="5"/>
              <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
              <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
              <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
              <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
            </svg>
            <span>Light</span>
          </button>
        </div>
      </div>
    </aside>

    <!-- 우측 메인 영역 -->
    <div class="flex flex-col flex-1 min-w-0">
      <!-- 이벤트 배너 토스트 -->
      <EventToast />

      <!-- 라우터 뷰 -->
      <main class="flex-1 overflow-auto">
        <router-view />
      </main>
    </div>
  </div>
</template>

<script setup>
import { ref, computed, provide } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import AppNav from './components/layout/AppNav.vue'
import EventToast from './components/dashboard/EventToast.vue'
// import { useWebSocket } from './composables/useWebSocket.js'
import { useChannelStore } from './stores/channelStore.js'
import { MAX_CHANNELS } from './constants/events.js'
import { useTheme } from './composables/useTheme.js'

// useWebSocket()

const { isDark, toggle } = useTheme()

const route = useRoute()
const isDashboard = computed(() => route.path === '/')

const { channels } = storeToRefs(useChannelStore())
const isMaxChannels = computed(() => channels.value.length >= MAX_CHANNELS)

const addModalSignal = ref(false)
provide('addModalSignal', addModalSignal)

function triggerAddModal() {
  if (isMaxChannels.value) return
  addModalSignal.value = true
}
</script>
