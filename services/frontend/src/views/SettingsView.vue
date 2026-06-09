<template>
  <div class="flex h-full" style="background: var(--bg-page); color: var(--text-primary);">
    <!-- 좌측 탭 목록 -->
    <aside class="w-56 flex-shrink-0 border-r py-6 px-3" style="border-color: var(--border); background: var(--bg-card);">
      <p class="text-xs font-semibold uppercase tracking-widest px-3 mb-3" style="color: var(--text-subtle);">설정</p>
      <nav class="flex flex-col gap-0.5">
        <button
          v-for="tab in tabs"
          :key="tab.id"
          class="flex items-center gap-3 w-full px-3 py-2 rounded-lg text-sm text-left transition-colors"
          :style="activeTab === tab.id
            ? 'background: var(--bg-elevated); color: var(--text-primary); font-weight: 500;'
            : 'color: var(--text-muted);'"
          @click="activeTab = tab.id"
        >
          <component :is="tab.icon" class="flex-shrink-0" />
          {{ tab.label }}
        </button>
      </nav>
    </aside>

    <!-- 우측 콘텐츠 -->
    <main class="flex-1 overflow-y-auto px-10 py-8">
      <!-- 계정 -->
      <section v-if="activeTab === 'account'">
        <h2 class="text-lg font-semibold mb-6">계정</h2>

        <div class="rounded-xl p-5 mb-4" style="background: var(--bg-card); border: 1px solid var(--border);">
          <div class="flex items-center gap-4">
            <div class="w-12 h-12 rounded-full flex items-center justify-center text-lg font-bold"
              style="background: var(--bg-elevated); color: var(--text-primary);">
              {{ auth.user?.username?.[0]?.toUpperCase() ?? '?' }}
            </div>
            <div>
              <p class="font-medium">{{ auth.user?.username ?? '-' }}</p>
              <span
                class="inline-block px-2 py-0.5 rounded text-xs font-semibold mt-1"
                :style="auth.isAdmin
                  ? 'background: #7f1d1d; color: #fca5a5;'
                  : 'background: #1f2937; color: #9ca3af;'"
              >{{ auth.isAdmin ? 'Admin' : 'Viewer' }}</span>
            </div>
          </div>
        </div>

        <div class="rounded-xl p-5" style="background: var(--bg-card); border: 1px solid var(--border);">
          <p class="text-sm font-medium mb-3">세션</p>
          <button
            class="flex items-center gap-2 px-4 py-2 rounded-lg text-sm transition-colors"
            style="background: var(--bg-elevated); color: var(--text-muted);"
            @click="handleLogout"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4M16 17l5-5-5-5M21 12H9"/>
            </svg>
            로그아웃
          </button>
        </div>
      </section>

      <!-- 나머지 탭 — 임시 placeholder -->
      <section v-else>
        <h2 class="text-lg font-semibold mb-6">{{ tabs.find(t => t.id === activeTab)?.label }}</h2>
        <div class="rounded-xl p-8 flex items-center justify-center"
          style="background: var(--bg-card); border: 1px solid var(--border); color: var(--text-subtle);">
          <p class="text-sm">준비 중입니다.</p>
        </div>
      </section>
    </main>
  </div>
</template>

<script setup>
import { ref, h } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore.js'

const auth = useAuthStore()
const router = useRouter()

const activeTab = ref('account')

function IconAccount() {
  return h('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.8 }, [
    h('circle', { cx: 12, cy: 8, r: 4 }),
    h('path', { d: 'M4 20c0-4 3.6-7 8-7s8 3 8 7' }),
  ])
}

function IconBell() {
  return h('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.8 }, [
    h('path', { d: 'M18 8a6 6 0 00-12 0c0 7-3 9-3 9h18s-3-2-3-9' }),
    h('path', { d: 'M13.73 21a2 2 0 01-3.46 0' }),
  ])
}

function IconSystem() {
  return h('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.8 }, [
    h('rect', { x: 2, y: 3, width: 20, height: 14, rx: 2 }),
    h('path', { d: 'M8 21h8M12 17v4' }),
  ])
}

function IconNetwork() {
  return h('svg', { width: 16, height: 16, viewBox: '0 0 24 24', fill: 'none', stroke: 'currentColor', 'stroke-width': 1.8 }, [
    h('circle', { cx: 12, cy: 5, r: 2 }),
    h('circle', { cx: 5, cy: 19, r: 2 }),
    h('circle', { cx: 19, cy: 19, r: 2 }),
    h('path', { d: 'M12 7v4M12 11l-5 6M12 11l5 6' }),
  ])
}

const tabs = [
  { id: 'account',      label: '계정',      icon: IconAccount },
  { id: 'notification', label: '알림',      icon: IconBell },
  { id: 'system',       label: '시스템',    icon: IconSystem },
  { id: 'network',      label: '네트워크',  icon: IconNetwork },
]

async function handleLogout() {
  await auth.logout()
  router.replace({ name: 'login' })
}
</script>
