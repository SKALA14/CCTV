<template>
  <div class="p-6 max-w-2xl mx-auto">
    <h1 class="text-lg font-bold mb-5" style="color: var(--text-primary);">프로필</h1>

    <!-- 계정 정보 -->
    <section class="rounded-2xl p-5 mb-4" style="background: var(--bg-card); border: 1px solid var(--border);">
      <div class="flex items-center gap-4">
        <div
          class="w-14 h-14 rounded-full flex items-center justify-center text-xl font-semibold flex-shrink-0"
          :style="avatarStyle"
        >{{ userInitial }}</div>
        <div class="min-w-0">
          <p class="font-medium truncate" style="color: var(--text-primary);">{{ auth.user?.username ?? '-' }}</p>
          <div class="flex items-center gap-2 mt-1.5">
            <span class="text-[10px] font-bold uppercase tracking-wider px-2 py-0.5 rounded" :style="badgeStyle">{{ roleLabel }}</span>
            <span class="text-xs" style="color: var(--text-muted);">{{ siteLabel }}</span>
          </div>
        </div>
      </div>
    </section>

    <!-- 비밀번호 변경 -->
    <section class="rounded-2xl p-5 mb-4" style="background: var(--bg-card); border: 1px solid var(--border);">
      <h2 class="text-sm font-semibold mb-3" style="color: var(--text-primary);">비밀번호 변경</h2>
      <form @submit.prevent="handlePassword" class="space-y-2.5" style="max-width: 22rem;">
        <input
          v-model="pw.current_password"
          type="password"
          placeholder="현재 비밀번호"
          autocomplete="current-password"
          class="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
          style="background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);"
        />
        <input
          v-model="pw.new_password"
          type="password"
          placeholder="새 비밀번호 (8자 이상, 영문+숫자 포함)"
          autocomplete="new-password"
          class="w-full px-4 py-2.5 rounded-xl text-sm outline-none"
          style="background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);"
        />
        <p v-if="pwError" class="text-red-400 text-xs px-1">{{ pwError }}</p>
        <p v-if="pwSaved" class="text-xs px-1" style="color: var(--green);">비밀번호가 변경되었습니다.</p>
        <button
          type="submit"
          :disabled="pwLoading || !pw.current_password || !pw.new_password"
          class="px-5 py-2.5 rounded-xl text-sm font-semibold transition-opacity"
          :class="(pwLoading || !pw.current_password || !pw.new_password) ? 'opacity-50 cursor-not-allowed' : ''"
          style="background: #2563eb; color: white;"
        >{{ pwLoading ? '변경 중...' : '비밀번호 변경' }}</button>
      </form>
    </section>

    <!-- 화면 테마 -->
    <section class="rounded-2xl p-5 mb-4 flex items-center justify-between" style="background: var(--bg-card); border: 1px solid var(--border);">
      <div>
        <h2 class="text-sm font-semibold" style="color: var(--text-primary);">화면 테마</h2>
        <p class="text-xs mt-0.5" style="color: var(--text-muted);">{{ isDark ? '다크 모드' : '라이트 모드' }}</p>
      </div>
      <button
        @click="toggle()"
        class="px-4 py-2 rounded-xl text-sm transition-colors"
        style="background: var(--bg-elevated); color: var(--text-muted); border: 1px solid var(--border);"
      >{{ isDark ? '라이트로 전환' : '다크로 전환' }}</button>
    </section>

    <!-- 세션 -->
    <section class="rounded-2xl p-5 flex items-center justify-between" style="background: var(--bg-card); border: 1px solid var(--border);">
      <div>
        <h2 class="text-sm font-semibold" style="color: var(--text-primary);">세션</h2>
        <p class="text-xs mt-0.5" style="color: var(--text-muted);">현재 계정에서 로그아웃합니다.</p>
      </div>
      <button
        @click="handleLogout"
        class="px-4 py-2 rounded-xl text-sm font-medium transition-colors"
        style="background: rgba(220,38,38,0.12); color: #f87171; border: 1px solid rgba(220,38,38,0.3);"
      >로그아웃</button>
    </section>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore.js'
import { useTheme } from '../composables/useTheme.js'
import { changeMyPassword } from '../api/users.js'

const auth = useAuthStore()
const router = useRouter()
const { isDark, toggle } = useTheme()

const roleLabel = computed(() => auth.isSuperadmin ? 'SUPER' : auth.isAdmin ? 'ADMIN' : 'VIEW')
const userInitial = computed(() => (auth.user?.username?.[0] ?? '?').toUpperCase())
const siteLabel = computed(() => auth.user?.site_name || (auth.isSuperadmin ? '전체 현장' : '—'))
const badgeStyle = computed(() =>
  auth.isSuperadmin ? 'background:#1e3a8a;color:#93c5fd;'
    : auth.isAdmin  ? 'background:#7f1d1d;color:#fca5a5;'
    :                 'background:#1f2937;color:#9ca3af;'
)
const avatarStyle = computed(() =>
  auth.isSuperadmin ? 'background:rgba(30,58,138,0.3);color:#93c5fd;'
    : auth.isAdmin  ? 'background:rgba(127,29,29,0.3);color:#fca5a5;'
    :                 'background:var(--bg-elevated);color:var(--text-muted);'
)

const pw = ref({ current_password: '', new_password: '' })
const pwLoading = ref(false)
const pwError = ref('')
const pwSaved = ref(false)

async function handlePassword() {
  pwLoading.value = true
  pwError.value = ''
  pwSaved.value = false
  try {
    await changeMyPassword(pw.value)
    await auth.fetchMe()
    pw.value = { current_password: '', new_password: '' }
    pwSaved.value = true
  } catch (e) {
    pwError.value = e.response?.data?.detail ?? e.message
  } finally {
    pwLoading.value = false
  }
}

async function handleLogout() {
  await auth.logout()
  router.replace({ name: 'login' })
}
</script>
