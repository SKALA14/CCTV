<!-- 내 프로필 화면 -->
<template>
  <div class="profile-page" :class="{ dark: isDark }">
    <div class="profile-inner">
      <!-- Page Header -->
      <div class="page-header">
        <div class="page-header-icon">
          <i class="ri-user-3-line"></i>
        </div>
        <div>
          <h1 class="page-title">Profile</h1>
          <p class="page-desc">{{ greeting }}</p>
        </div>
      </div>

      <!-- 계정 정보 -->
      <section class="card card-glow">
        <div class="account-row">
          <div class="avatar" :style="avatarStyle">{{ userInitial }}</div>
          <div class="account-info">
            <p class="account-name">{{ auth.user?.username ?? '-' }}</p>
            <div class="account-meta">
              <span class="role-badge" :style="badgeStyle">{{ roleLabel }}</span>
              <span class="account-site">{{ siteLabel }}</span>
            </div>
            <p class="account-login">마지막 접속 · {{ lastLoginLabel }}</p>
          </div>
        </div>
      </section>

      <!-- 비밀번호 변경 -->
      <section class="card card-glow">
        <h2 class="section-title">비밀번호 변경</h2>
        <form @submit.prevent="handlePassword" class="pw-form">
          <input
            v-model="pw.current_password"
            type="password"
            placeholder="현재 비밀번호"
            autocomplete="current-password"
            class="form-input"
          />
          <input
            v-model="pw.new_password"
            type="password"
            placeholder="새 비밀번호 (8자 이상, 영문+숫자 포함)"
            autocomplete="new-password"
            class="form-input"
          />
          <p v-if="pwError" class="form-error-text">{{ pwError }}</p>
          <p v-if="pwSaved" class="form-success-text">
            <i class="ri-check-line"></i> 비밀번호가 변경되었습니다.
          </p>
          <button
            type="submit"
            :disabled="pwLoading || !pw.current_password || !pw.new_password"
            class="btn-primary"
          >{{ pwLoading ? '변경 중...' : '비밀번호 변경' }}</button>
        </form>
      </section>

      <!-- 화면 테마 -->
      <section class="card card-glow card-row-between">
        <div>
          <h2 class="section-title">화면 테마</h2>
          <p class="section-hint">{{ isDark ? '다크 모드' : '라이트 모드' }}</p>
        </div>
        <button class="btn-ghost" @click="toggle()">
          <i :class="isDark ? 'ri-sun-line' : 'ri-moon-line'"></i>
          {{ isDark ? '라이트로 전환' : '다크로 전환' }}
        </button>
      </section>

      <!-- 세션 -->
      <section class="card card-glow card-row-between">
        <div>
          <h2 class="section-title">세션</h2>
          <p class="section-hint">현재 계정에서 로그아웃합니다.</p>
        </div>
        <button class="btn-logout" @click="handleLogout">로그아웃</button>
      </section>
    </div>
  </div>
</template>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore.js'
import { useTheme } from '../composables/useTheme.js'
import { changeMyPassword } from '../api/users.js'
import { getAvatarText } from '../utils/userAvatar.js'

const auth   = useAuthStore()
const router = useRouter()
const { isDark, toggle } = useTheme()

const roleLabel   = computed(() => auth.isAdmin ? 'ADMIN' : 'USER')
const userInitial = computed(() => getAvatarText(auth.user?.username))
const siteLabel   = computed(() => auth.user?.site_name || '—')

const greeting = computed(() => {
  const h    = new Date().getHours()
  const part = h < 6 ? '늦은 밤이에요' : h < 12 ? '좋은 아침이에요' : h < 18 ? '오후 근무 중이시네요' : '야간 근무 중이시네요'
  return `${auth.user?.username ?? ''}님, ${part} 👋`
})

const lastLoginLabel = computed(() => {
  const iso = auth.user?.last_login
  if (!iso) return '기록 없음'
  const diff = Date.now() - new Date(iso).getTime()
  if (Number.isNaN(diff)) return '기록 없음'
  const m = Math.floor(diff / 60000)
  if (m < 1) return '방금 전'
  if (m < 60) return `${m}분 전`
  const hh = Math.floor(m / 60)
  if (hh < 24) return `${hh}시간 전`
  return new Date(iso).toLocaleString('ko-KR', { month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit' })
})

const badgeStyle = computed(() =>
  auth.isAdmin
    ? 'background:#7f1d1d; color:#fca5a5;'
    : 'background: var(--c-bg-elevated); color: var(--c-text-muted); border: 1px solid var(--c-border);'
)
const avatarStyle = computed(() =>
  auth.isAdmin
    ? 'background:rgba(127,29,29,0.3); color:#fca5a5;'
    : 'background: var(--c-bg-elevated); color: var(--c-text-muted);'
)

const pw        = ref({ current_password: '', new_password: '' })
const pwLoading = ref(false)
const pwError   = ref('')
const pwSaved   = ref(false)

async function handlePassword() {
  pwLoading.value = true
  pwError.value   = ''
  pwSaved.value   = false
  try {
    await changeMyPassword(pw.value)
    await auth.fetchMe()
    pw.value  = { current_password: '', new_password: '' }
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

<style scoped>
/* ══ Design Tokens ══ */
.profile-page {
  --c-bg:             #f9fafb;
  --c-bg-card:        #ffffff;
  --c-bg-elevated:    #f3f4f6;
  --c-border:         #e5e7eb;
  --c-border-light:   #f0f0f0;
  --c-text:           #111827;
  --c-text-secondary: #4b5563;
  --c-text-muted:     #9ca3af;
  --c-accent:         #77942e;
  --c-accent-soft:    #eef2df;
  --c-accent-border:  #b6c77a;
  --c-accent-hover:   #64731e;
  --c-red:            #ef4444;
  --c-green:          #22c55e;
  min-height: 100%;
  background: var(--c-bg);
  color: var(--c-text);
  font-family: 'Pretendard Variable', Pretendard, -apple-system, system-ui, sans-serif;
  font-size: 14px;
  -webkit-font-smoothing: antialiased;
  transition: background 0.3s, color 0.3s;
}

.profile-page.dark {
  --c-bg:             #111827;
  --c-bg-card:        #1a1f2e;
  --c-bg-elevated:    #1f2937;
  --c-border:         #2d3548;
  --c-border-light:   #263040;
  --c-text:           #f3f4f6;
  --c-text-secondary: #9ca3af;
  --c-text-muted:     #6b7280;
  --c-accent-soft:    #263112;
  --c-accent-border:  #4d6420;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
button { font-family: inherit; cursor: pointer; }
input  { font-family: inherit; }
i { display: inline-flex; align-items: center; justify-content: center; }

/* ══ Layout ══ */
.profile-inner {
  max-width: 640px;
  margin: 0 auto;
  padding: 28px 24px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ══ Page Header ══ */
.page-header { display: flex; align-items: center; gap: 10px; margin-bottom: 4px; }
.page-header-icon {
  width: 32px; height: 32px; border-radius: 10px; flex-shrink: 0;
  background: var(--c-accent-soft); display: flex; align-items: center; justify-content: center;
}
.page-header-icon i { color: var(--c-accent-hover); font-size: 15px; }
.page-title { font-size: 18px; font-weight: 700; color: var(--c-text); }
.page-desc  { font-size: 12px; color: var(--c-text-muted); margin-top: 2px; }

/* ══ Card ══ */
.card {
  background: var(--c-bg-card);
  border: 1px solid var(--c-border-light);
  border-radius: 14px;
  padding: 20px;
  transition: background 0.3s, border 0.3s;
}
.card-glow { position: relative; overflow: hidden; }
.card-glow::before {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(ellipse at 50% 0%, rgba(132,204,22,0.04) 0%, transparent 70%);
}
.card-row-between { display: flex; align-items: center; justify-content: space-between; gap: 16px; }

/* ══ Account Row ══ */
.account-row { display: flex; align-items: center; gap: 16px; }
.avatar {
  width: 52px; height: 52px; border-radius: 50%; flex-shrink: 0;
  display: flex; align-items: center; justify-content: center;
  font-size: 18px; font-weight: 600;
}
.account-info  { display: flex; flex-direction: column; gap: 4px; min-width: 0; }
.account-name  { font-size: 15px; font-weight: 600; color: var(--c-text); }
.account-meta  { display: flex; align-items: center; gap: 8px; }
.account-site  { font-size: 12px; color: var(--c-text-muted); }
.account-login { font-size: 11px; color: var(--c-text-muted); }

.role-badge {
  font-size: 10px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.06em;
  padding: 2px 8px; border-radius: 5px;
}

/* ══ Section ══ */
.section-title { font-size: 13px; font-weight: 600; color: var(--c-text); margin-bottom: 2px; }
.section-hint  { font-size: 12px; color: var(--c-text-muted); }

/* ══ Password Form ══ */
.pw-form { display: flex; flex-direction: column; gap: 10px; max-width: 360px; margin-top: 14px; }
.form-input {
  width: 100%; padding: 9px 14px; border-radius: 10px;
  border: 1px solid var(--c-border); background: var(--c-bg-elevated);
  color: var(--c-text); font-size: 13px; outline: none;
  transition: border-color 0.15s, box-shadow 0.15s;
}
.form-input:focus {
  border-color: var(--c-accent-border);
  box-shadow: 0 0 0 3px rgba(132,204,22,0.1);
}
.form-input::placeholder { color: var(--c-text-muted); }
.form-error-text   { font-size: 12px; color: var(--c-red); padding: 0 2px; }
.form-success-text { font-size: 12px; color: var(--c-green); padding: 0 2px; display: flex; align-items: center; gap: 4px; }

/* ══ Buttons ══ */
.btn-primary {
  display: inline-flex; align-items: center; justify-content: center;
  padding: 9px 20px; border-radius: 10px; border: none;
  background: #2563eb; color: #fff;
  font-size: 13px; font-weight: 600; transition: opacity 0.2s;
  align-self: flex-start;
}
.btn-primary:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-primary:not(:disabled):hover { opacity: 0.88; }

.btn-ghost {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 8px 16px; border-radius: 10px;
  border: 1px solid var(--c-border); background: var(--c-bg-elevated);
  color: var(--c-text-secondary); font-size: 13px; font-weight: 500;
  transition: all 0.15s; white-space: nowrap;
}
.btn-ghost:hover { background: var(--c-border); color: var(--c-text); }

.btn-logout {
  padding: 8px 16px; border-radius: 10px;
  border: 1px solid rgba(220,38,38,0.3);
  background: rgba(220,38,38,0.08); color: #f87171;
  font-size: 13px; font-weight: 500; transition: all 0.15s; white-space: nowrap;
}
.btn-logout:hover { background: rgba(220,38,38,0.15); }
</style>
