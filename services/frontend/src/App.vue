<template>
  <div class="flex h-full">
    <!-- 좌측 사이드바 (로그인 등 공개 페이지에서는 숨김) -->
    <aside
      v-if="!route.meta.public"
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

      <!-- 채널 추가 버튼 (대시보드 + admin 역할만) -->
      <div v-if="isDashboard && authStore.user?.role === 'admin'" class="mt-2 px-2 w-full">
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

      <!-- superadmin 전용 관리 메뉴 -->
      <div v-if="authStore.isSuperadmin" class="px-2 w-full mb-1">
        <router-link :to="{ name: 'admin' }" custom v-slot="{ navigate, isActive }">
          <button
            @click="navigate"
            class="flex flex-col items-center gap-1 w-full py-2.5 rounded-xl text-[9px] font-semibold transition-colors"
            :style="isActive
              ? 'background: var(--bg-elevated); color: #60a5fa;'
              : 'background: var(--bg-elevated); color: var(--text-muted);'"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/>
              <circle cx="9" cy="7" r="4"/>
              <path d="M23 21v-2a4 4 0 00-3-3.87"/>
              <path d="M16 3.13a4 4 0 010 7.75"/>
            </svg>
            <span>관리</span>
          </button>
        </router-link>
      </div>

      <!-- 사용자 정보 + 로그아웃 -->
      <div v-if="authStore.isLoggedIn" class="px-2 w-full mb-1">
        <div class="mb-2" style="border-top: 1px solid var(--border);"></div>
        <div class="flex justify-center mb-1">
          <span
            class="px-1.5 py-0.5 rounded text-[8px] font-bold uppercase tracking-wider"
            :style="authStore.isSuperadmin
              ? 'background: #1e3a8a; color: #93c5fd;'
              : authStore.isAdmin
                ? 'background: #7f1d1d; color: #fca5a5;'
                : 'background: #1f2937; color: #9ca3af;'"
          >{{ authStore.isSuperadmin ? 'SUPER' : authStore.isAdmin ? 'ADMIN' : 'VIEW' }}</span>
        </div>
        <button
          class="flex flex-col items-center gap-1 w-full py-2.5 rounded-xl text-[9px] font-semibold transition-colors"
          style="background: var(--bg-elevated); color: var(--text-muted);"
          @click="handleLogout"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
          </svg>
          <span>로그아웃</span>
        </button>
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
import { ref, computed, provide, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
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
const router = useRouter()
const isDashboard = computed(() => route.path === '/')

const authStore = useAuthStore()

async function handleLogout() {
  await authStore.logout()
  router.replace({ name: 'login' })
}

const channelStore = useChannelStore()

const isMaxChannels = computed(() => channelStore.slots.filter(Boolean).length >= 4)

const addModalSignal = ref(false)
provide('addModalSignal', addModalSignal)

function triggerAddModal() {
  addModalSignal.value = true
}

// 로그인·로그아웃·계정 전환 시 채널 스토어를 리셋하고 새로 로드
watch(() => authStore.user, async (newUser) => {
    channelStore.resetSlots()
    if (!newUser || newUser.role === 'superadmin') return
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
}, { immediate: true })
</script>
