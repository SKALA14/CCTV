<template>
  <div class="flex h-full">
    <!-- 좌측 사이드바 (로그인·월 등 크롬 없는 화면에서는 숨김) -->
    <aside
      v-if="!route.meta.public && !route.meta.bare"
      class="flex flex-col items-center w-16 border-r flex-shrink-0 py-3"
      style="background: var(--bg-card); border-color: var(--border);"
    >
      <!-- 앱 로고 -->
      <div class="mb-5 flex flex-col items-center">
        <svg width="28" height="32" viewBox="0 0 28 32" fill="none">
          <circle cx="14" cy="13" r="13" fill="#1e293b" stroke="#334155" stroke-width="0.8"/>
          <circle cx="14" cy="13" r="10" fill="#e2e8f0"/>
          <circle cx="14" cy="13" r="8" fill="#1e293b"/>
          <circle cx="14" cy="13" r="5" fill="#f1f5f9"/>
          <circle cx="14" cy="13" r="3.2" fill="#0f172a"/>
          <circle cx="11.8" cy="10.8" r="1.3" fill="white" opacity="0.85"/>
          <circle cx="15.5" cy="14" r="0.6" fill="white" opacity="0.6"/>
          <ellipse cx="14" cy="28" rx="6.5" ry="1.6" fill="#1e293b" stroke="#334155" stroke-width="0.8"/>
          <rect x="11.5" y="25.5" width="5" height="3.5" rx="0.5" fill="#1e293b" stroke="#334155" stroke-width="0.8"/>
        </svg>
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
        <div v-if="isLiveView" style="height: 100%">
          <DashboardView />
        </div>
        <router-view v-if="!isLiveView" v-slot="{ Component }">
          <keep-alive include="ManualView,ZoneView">
            <component :is="Component" />
          </keep-alive>
        </router-view>
      </main>
    </div>
  </div>

  <!-- 우하단 알림 토스트 (어느 페이지에서나 표시) -->
  <NotificationToast />
</template>

<script setup>
import { computed, watch, ref, onMounted, onUnmounted } from 'vue'
import { useRoute } from 'vue-router'
import AppNav from './components/layout/AppNav.vue'
import DashboardView from './views/DashboardView.vue'
import NotificationToast from './components/dashboard/NotificationToast.vue'
import { useWebSocket } from './composables/useWebSocket.js'
import { useChannelStore } from './stores/channelStore.js'
import { useTheme } from './composables/useTheme.js'
import { getChannels } from './api/channels.js'
import { getHealth } from './api/status.js'
import { useAuthStore } from './stores/authStore.js'

useWebSocket()

useTheme()   // 모듈 로드 시 전역 테마 적용 (토글은 프로필 페이지에서)

const route = useRoute()
// 라이브 그리드(DashboardView)를 보여줄 경로 — 관제(월) 홈
const isLiveView = computed(() => route.path === '/wall')

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

// 시스템 상태 점등 — 자기 현장 채널 온라인 n/N (전 계정)
const health = ref({ online: 0, total: 0 })
const healthColor = computed(() =>
  health.value.total === 0 ? '#48484a'
    : health.value.online === health.value.total ? '#22c55e'
    : health.value.online === 0 ? '#dc2626' : '#f59e0b'
)
const healthTitle = computed(() =>
  health.value.online === health.value.total ? '전체 정상' : `${health.value.total - health.value.online}대 점검 필요`
)
let _healthTimer
async function loadHealth() {
  if (!authStore.isLoggedIn) return
  try { health.value = await getHealth() } catch { /* 무시 */ }
}
onMounted(() => { loadHealth(); _healthTimer = setInterval(loadHealth, 30000) })
onUnmounted(() => clearInterval(_healthTimer))
watch(() => authStore.user, loadHealth)

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
