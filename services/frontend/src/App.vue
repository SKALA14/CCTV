<!-- 루트 컴포넌트 — 사이드바 레이아웃 + 라우터 뷰 -->
<template>
  <div class="flex h-full">
    <!-- 좌측 사이드바 (로그인·월 등 크롬 없는 화면에서는 숨김) -->
    <aside
      v-if="!route.meta.public && !route.meta.bare"
      class="flex flex-col flex-shrink-0 border-r py-4"
      style="background: var(--bg-card); border-color: var(--border); width: 220px;"
    >
      <!-- 앱 로고 -->
      <div class="flex items-center gap-2 px-5 mb-6">
        <img src="/pic.png" alt="" style="height:32px; object-fit:contain;"/>
        <img src="/letter.png" alt="SIREN" style="height:20px; object-fit:contain;"/>
      </div>

      <!-- 네비게이션 -->
      <AppNav class="w-full px-3" />

      <div class="flex-1"></div>
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
