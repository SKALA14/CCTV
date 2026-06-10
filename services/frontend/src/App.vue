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
            : 'bg-blue-600 text-white hover:bg-blue-500'"
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

      <!-- 프로필 진입 (모든 역할) — 계정·비밀번호·테마·로그아웃은 프로필 페이지에서 -->
      <div v-if="authStore.isLoggedIn" class="w-full px-1.5 flex flex-col items-center">
        <div class="nav-divider"></div>
        <router-link to="/profile" class="nav-tab" active-class="active" :title="accountTitle">
          <div
            class="w-8 h-8 rounded-full flex items-center justify-center text-xs font-semibold"
            :style="avatarStyle"
          >{{ userInitial }}</div>
          <span>프로필</span>
        </router-link>
      </div>
    </aside>

    <!-- 우측 메인 영역 -->
    <div class="flex flex-col flex-1 min-w-0">
      <!-- 라우터 뷰 -->
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

  <!-- 우하단 알림 토스트 (어느 페이지에서나 표시) -->
  <NotificationToast />
</template>

<script setup>
import { ref, computed, provide, watch } from 'vue'
import { useRoute } from 'vue-router'
import { storeToRefs } from 'pinia'
import AppNav from './components/layout/AppNav.vue'
import DashboardView from './views/DashboardView.vue'
import NotificationToast from './components/dashboard/NotificationToast.vue'
import { useWebSocket } from './composables/useWebSocket.js'
import { useChannelStore } from './stores/channelStore.js'
import { useTheme } from './composables/useTheme.js'
import { getChannels } from './api/channels.js'
import { useAuthStore } from './stores/authStore.js'

useWebSocket()

useTheme()   // 모듈 로드 시 전역 테마 적용 (토글은 프로필 페이지에서)

const route = useRoute()
const isDashboard = computed(() => route.path === '/')

const authStore = useAuthStore()

// 사이드바 프로필 진입점 — 아바타(이니셜·역할색) + hover 툴팁
const userInitial = computed(() => (authStore.user?.username?.[0] ?? '?').toUpperCase())
const accountTitle = computed(() => {
  const u = authStore.user
  if (!u) return ''
  const site = u.site_name || (authStore.isSuperadmin ? '전체 현장' : '—')
  return `${u.username} · ${site}`
})
const avatarStyle = computed(() =>
  authStore.isSuperadmin ? 'background:rgba(30,58,138,0.3);color:#93c5fd;'
    : authStore.isAdmin  ? 'background:rgba(127,29,29,0.3);color:#fca5a5;'
    :                      'background:var(--bg-elevated);color:var(--text-muted);'
)

const channelStore = useChannelStore()
const { slots } = storeToRefs(channelStore)
const isMaxChannels = computed(() => slots.value.every(s => s !== null))

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

const addModalSignal = ref(false)
provide('addModalSignal', addModalSignal)

function triggerAddModal() {
  if (isMaxChannels.value) return
  addModalSignal.value = true
}
</script>
