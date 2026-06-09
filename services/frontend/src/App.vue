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

      <div class="flex-1"></div>

      <!-- 설정 버튼 -->
      <div class="px-2 w-full mb-1">
        <router-link
          to="/settings"
          class="nav-tab w-full"
          active-class="active"
        >
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/>
          </svg>
          <span>설정</span>
        </router-link>
      </div>

      <!-- 테마 토글 -->
      <div class="px-2 w-full">
        <div class="mb-2" style="border-top: 1px solid var(--border);"></div>
        <button
          class="flex flex-col items-center gap-1 w-full py-2.5 rounded-xl text-[9px] font-semibold transition-colors"
          style="background: var(--bg-elevated); color: var(--text-muted);"
          @click="toggle()"
        >
          <svg v-if="isDark" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/>
          </svg>
          <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="5"/>
            <line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
            <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
            <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
            <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
          </svg>
          <span>{{ isDark ? 'Dark' : 'Light' }}</span>
        </button>
      </div>
    </aside>

    <!-- 우측 메인 영역 -->
    <div class="flex flex-col flex-1 min-w-0">
      <main class="flex-1 overflow-auto" style="position: relative;">
        <div :style="isDashboard ? 'height: 100%' : 'visibility: hidden; position: absolute; inset: 0; pointer-events: none'">
          <DashboardView />
        </div>
        <keep-alive include="ManualView">
          <router-view v-if="!isDashboard" />
        </keep-alive>
      </main>
    </div>
  </div>

  <!-- 우하단 알림 토스트 -->
  <NotificationToast />
</template>

<script setup>
import { ref, computed, provide, onMounted } from 'vue'
import { useRoute } from 'vue-router'
import AppNav from './components/layout/AppNav.vue'
import DashboardView from './views/DashboardView.vue'
import NotificationToast from './components/dashboard/NotificationToast.vue'
import { useWebSocket } from './composables/useWebSocket.js'
import { useChannelStore } from './stores/channelStore.js'
import { useTheme } from './composables/useTheme.js'
import { getChannels } from './api/channels.js'
import { useAuthStore } from './stores/authStore.js'

useWebSocket()

const { isDark, toggle } = useTheme()

const route = useRoute()
const isDashboard = computed(() => route.path === '/')

const authStore = useAuthStore()

const channelStore = useChannelStore()

onMounted(async () => {
  try {
    const res = await getChannels()
    res.data.forEach(ch => {
      if (channelStore.slots[ch.slot] === null) {
        channelStore.addChannel(ch.slot, ch)
      }
    })
  } catch (e) {
    console.warn('채널 복구 실패:', e.message)
  }
})

const addModalSignal = ref(false)
provide('addModalSignal', addModalSignal)
</script>
