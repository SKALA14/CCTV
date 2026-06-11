<template>
  <div class="flex h-full">
    <!-- 좌측 사이드바 (로그인·월 등 크롬 없는 화면에서는 숨김) -->
    <aside
      v-if="!route.meta.public && !route.meta.bare"
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
        <div :style="isLiveView ? 'height: 100%' : 'visibility: hidden; position: absolute; inset: 0; pointer-events: none'">
          <DashboardView />
        </div>
        <keep-alive include="ManualView">
          <router-view v-if="!isLiveView" />
        </keep-alive>
      </main>
    </div>
  </div>

  <!-- 전체화면 관제(월)에서 콘솔로 복귀 — 우상단 은은한 진입점 -->
  <router-link
    v-if="route.meta.bare"
    to="/"
    class="wall-exit"
    title="콘솔로 나가기"
  >
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8">
      <path d="M8 3v3a2 2 0 0 1-2 2H3M21 8h-3a2 2 0 0 1-2-2V3M3 16h3a2 2 0 0 1 2 2v3M16 21v-3a2 2 0 0 1 2-2h3" stroke-linecap="round" stroke-linejoin="round"/>
    </svg>
    <span>콘솔</span>
  </router-link>

  <!-- 우하단 알림 토스트 (어느 페이지에서나 표시) -->
  <NotificationToast />
</template>

<script setup>
import { computed, watch } from 'vue'
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

useTheme()   // 모듈 로드 시 전역 테마 적용 (토글은 프로필 페이지에서)

const route = useRoute()
// 라이브 그리드(DashboardView)를 보여줄 경로 — 콘솔 대시보드('/')와 월('/wall')
const isLiveView = computed(() => route.path === '/' || route.path === '/wall')

const authStore = useAuthStore()

// 사이드바 프로필 진입점 — 아바타(이니셜·역할색) + hover 툴팁
const userInitial = computed(() => (authStore.user?.username?.[0] ?? '?').toUpperCase())
const accountTitle = computed(() => {
  const u = authStore.user
  if (!u) return ''
  const site = u.site_name || '—'
  return `${u.username} · ${site}`
})
const avatarStyle = computed(() =>
  authStore.isAdmin ? 'background:rgba(127,29,29,0.3);color:#fca5a5;'
    :                 'background:var(--bg-elevated);color:var(--text-muted);'
)

const channelStore = useChannelStore()

// 로그인·로그아웃·계정 전환 시 채널 스토어를 리셋하고 새로 로드
watch(() => authStore.user, async (newUser) => {
    channelStore.resetSlots()
    if (!newUser) return
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

<style scoped>
/* 전체화면 관제(월)에서 콘솔로 복귀하는 우상단 진입점 — 24시간 화면을 가리지 않게 은은하게 */
.wall-exit {
  position: fixed;
  top: 14px;
  right: 14px;
  z-index: 40;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 12px;
  border-radius: 9999px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-muted);
  background: color-mix(in srgb, var(--bg-card) 70%, transparent);
  border: 1px solid var(--border);
  backdrop-filter: blur(8px);
  opacity: 0.35;
  transition: opacity 0.15s ease, color 0.15s ease;
}
.wall-exit:hover {
  opacity: 1;
  color: var(--text-primary);
}
</style>
