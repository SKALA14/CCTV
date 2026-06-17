<template>
  <div class="app-shell" :class="{ dark: isDark }">
    <div class="ambient ambient-a"></div>
    <div class="ambient ambient-b"></div>
    <div class="ambient ambient-c"></div>
    <main class="main-content">
      <div class="form-wrapper">
        <div class="card card-glow form-card">
          <!-- Form Header -->
          <div class="form-header">
            <div class="form-header-icon">
              <i class="ri-lock-line"></i>
            </div>
            <div>
              <h1 class="form-title">비밀번호 변경</h1>
              <p v-if="mustChangePwd" class="form-desc warn-desc">
                <i class="ri-error-warning-line"></i>
                계속하려면 초기 비밀번호를 반드시 변경해야 합니다.
              </p>
              <p v-else class="form-desc">새 비밀번호를 입력해주세요.</p>
            </div>
          </div>

          <div class="form-divider"></div>

          <!-- Form -->
          <form @submit.prevent="handleSubmit" class="form-body">
            <!-- Current Password -->
            <div class="field-group">
              <label class="field-label">
                <i class="ri-key-line"></i> 현재 비밀번호
              </label>
              <div class="field-input-wrap">
                <input
                  v-model="form.current_password"
                  :type="showCurrent ? 'text' : 'password'"
                  placeholder="현재 비밀번호를 입력하세요"
                  class="field-input"
                  autocomplete="current-password"
                />
                <button type="button" class="field-toggle" @click="showCurrent = !showCurrent" tabindex="-1">
                  <i :class="showCurrent ? 'ri-eye-off-line' : 'ri-eye-line'"></i>
                </button>
              </div>
            </div>

            <!-- New Password -->
            <div class="field-group">
              <label class="field-label">
                <i class="ri-lock-password-line"></i> 새 비밀번호
              </label>
              <div class="field-input-wrap">
                <input
                  v-model="form.new_password"
                  :type="showNew ? 'text' : 'password'"
                  placeholder="8+ chars, letters & numbers"
                  class="field-input"
                  autocomplete="new-password"
                />
                <button type="button" class="field-toggle" @click="showNew = !showNew" tabindex="-1">
                  <i :class="showNew ? 'ri-eye-off-line' : 'ri-eye-line'"></i>
                </button>
              </div>
              <!-- Password strength indicator -->
              <div v-if="form.new_password" class="pw-strength">
                <div class="pw-strength-bar">
                  <div class="pw-strength-fill" :class="'pw-strength-' + strengthLevel"></div>
                </div>
                <span class="pw-strength-text" :class="'pw-strength-text-' + strengthLevel">{{ strengthLabel }}</span>
              </div>
            </div>

            <!-- Confirm New Password -->
            <div class="field-group">
              <label class="field-label">
                <i class="ri-lock-password-line"></i> 새 비밀번호 확인
              </label>
              <div class="field-input-wrap">
                <input
                  v-model="form.confirm_password"
                  :type="showConfirm ? 'text' : 'password'"
                  placeholder="새 비밀번호를 다시 입력하세요"
                  class="field-input"
                  autocomplete="new-password"
                />
                <button type="button" class="field-toggle" @click="showConfirm = !showConfirm" tabindex="-1">
                  <i :class="showConfirm ? 'ri-eye-off-line' : 'ri-eye-line'"></i>
                </button>
              </div>
              <p v-if="form.confirm_password && form.new_password !== form.confirm_password" class="field-hint field-hint-error">
                <i class="ri-close-circle-line"></i> 비밀번호가 일치하지 않습니다
              </p>
              <p v-else-if="form.confirm_password && form.new_password === form.confirm_password" class="field-hint field-hint-ok">
                <i class="ri-check-line"></i> 비밀번호가 일치합니다
              </p>
            </div>

            <!-- Error Message -->
            <div v-if="error" class="error-box">
              <i class="ri-error-warning-line"></i>
              <p>{{ error }}</p>
            </div>

            <!-- Success Message -->
            <div v-if="success" class="success-box">
              <i class="ri-check-double-line"></i>
              <p>비밀번호가 변경되었습니다. 잠시 후 이동합니다...</p>
            </div>

            <!-- Submit -->
            <button
              type="submit"
              class="btn-submit"
              :disabled="loading || !canSubmit"
            >
              <span v-if="loading" class="spinner-text">
                <span class="spinner spinner-light-sm"></span> 변경 중...
              </span>
              <span v-else>비밀번호 변경</span>
            </button>

            <!-- Back Link -->
            <button v-if="!mustChangePwd" type="button" class="btn-back" @click="goBack">
              <i class="ri-arrow-left-line"></i> 돌아가기
            </button>
          </form>
        </div>

        <!-- Password Requirements Hint -->
        <div class="card card-glow pw-hint-card">
          <h3 class="pw-hint-title">
            <i class="ri-information-line"></i> 비밀번호 안내
          </h3>
          <ul class="pw-hint-list">
            <li :class="{ 'pw-hint-ok': form.new_password.length >= 8 }">
              <i :class="form.new_password.length >= 8 ? 'ri-check-line' : 'ri-subtract-line'"></i>
              8자 이상 입력
            </li>
            <li :class="{ 'pw-hint-ok': /[a-zA-Z]/.test(form.new_password) }">
              <i :class="/[a-zA-Z]/.test(form.new_password) ? 'ri-check-line' : 'ri-subtract-line'"></i>
              영문 포함
            </li>
            <li :class="{ 'pw-hint-ok': /\d/.test(form.new_password) }">
              <i :class="/\d/.test(form.new_password) ? 'ri-check-line' : 'ri-subtract-line'"></i>
              숫자 포함
            </li>
            <li :class="{ 'pw-hint-ok': /[^a-zA-Z0-9]/.test(form.new_password) }">
              <i :class="/[^a-zA-Z0-9]/.test(form.new_password) ? 'ri-check-line' : 'ri-subtract-line'"></i>
              특수문자 포함
            </li>
          </ul>
        </div>
      </div>
    </main>
  </div>
</template>

<script>
export default { name: 'PasswordChangeView' }
</script>

<script setup>
import { ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { useTheme } from '../composables/useTheme.js'
import { useAuthStore } from '../stores/authStore.js'
import { changeMyPassword } from '../api/users.js'

const router    = useRouter()
const authStore = useAuthStore()
const { isDark, toggle: toggleTheme } = useTheme()

const mustChangePwd = computed(() => authStore.mustChangePwd)

const form = ref({
  current_password: '',
  new_password: '',
  confirm_password: '',
})
const loading = ref(false)
const error   = ref('')
const success = ref(false)

const showCurrent = ref(false)
const showNew     = ref(false)
const showConfirm = ref(false)

/* ── Computed ── */
const strengthScore = computed(() => {
  let score = 0
  const pw = form.value.new_password
  if (pw.length >= 8) score++
  if (pw.length >= 12) score++
  if (/[a-zA-Z]/.test(pw)) score++
  if (/\d/.test(pw)) score++
  if (/[^a-zA-Z0-9]/.test(pw)) score++
  return Math.min(score, 5)
})

const strengthLevel = computed(() => {
  if (strengthScore.value <= 1) return 'weak'
  if (strengthScore.value <= 3) return 'medium'
  return 'strong'
})

const strengthLabel = computed(() => {
  if (!form.value.new_password) return ''
  if (strengthScore.value <= 1) return '약함'
  if (strengthScore.value <= 3) return '보통'
  return '강함'
})

const canSubmit = computed(() =>
  form.value.current_password &&
  form.value.new_password &&
  form.value.confirm_password &&
  form.value.new_password === form.value.confirm_password &&
  form.value.new_password.length >= 8 &&
  !loading.value &&
  !success.value
)

/* ── Methods ── */
function goBack() {
  router.back()
}

async function handleSubmit() {
  if (!canSubmit.value) return
  loading.value = true
  error.value   = ''
  success.value = false
  try {
    await changeMyPassword({
      current_password: form.value.current_password,
      new_password: form.value.new_password,
    })
    // must_change_password 플래그 갱신 후 관제 화면으로
    await authStore.fetchMe()
    success.value = true
    setTimeout(() => router.replace({ name: 'wall' }), 1200)
  } catch (e) {
    error.value = e.response?.data?.detail ?? e.message ?? '비밀번호 변경 중 오류가 발생했습니다.'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
/* ═══════════════════════════ Design System ═══════════════════════════ */
.app-shell {
  --c-bg: #f9fafb;
  --c-bg-card: #ffffff;
  --c-bg-elevated: #f3f4f6;
  --c-border: #e5e7eb;
  --c-border-light: #f0f0f0;
  --c-text: #111827;
  --c-text-secondary: #4b5563;
  --c-text-muted: #9ca3af;
  --c-accent: #77942e;
  --c-accent-soft: #eef2df;
  --c-accent-border: #b6c77a;
  --c-accent-hover: #64731e;
  --c-red: #ef4444;
  --c-red-soft: #fef2f2;
  --c-green: #22c55e;
  --c-green-soft: #f0fdf4;
  --c-amber: #f59e0b;
  --c-amber-soft: #fffbeb;
  --c-orange: #f97316;
}

.app-shell.dark {
  background:
    radial-gradient(circle at top left, rgba(119,148,46,0.16), transparent 26%),
    radial-gradient(circle at bottom right, rgba(182,199,122,0.10), transparent 30%),
    linear-gradient(180deg, #0f140b 0%, #141b10 100%);
  --c-bg: #111827;
  --c-bg-card: #1a1f2e;
  --c-bg-elevated: #1f2937;
  --c-border: #2d3548;
  --c-border-light: #263040;
  --c-text: #f3f4f6;
  --c-text-secondary: #9ca3af;
  --c-text-muted: #6b7280;
  --c-accent-soft: #263112;
  --c-accent-border: #4d6420;
  --c-red-soft: #2d1215;
  --c-green-soft: #122a1a;
  --c-amber-soft: #2d2010;
}

/* ═══════════════════════════ Base ═══════════════════════════ */
.app-shell {
  min-height: 100vh;
  background:
    radial-gradient(circle at top left, rgba(119,148,46,0.14), transparent 26%),
    radial-gradient(circle at bottom right, rgba(182,199,122,0.14), transparent 28%),
    linear-gradient(180deg, #f7f9f3 0%, #eef2e3 100%);
  color: var(--c-text);
  font-family: 'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  transition: background 0.3s, color 0.3s;
  -webkit-font-smoothing: antialiased;
  position: relative;
  overflow: hidden;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

button { font-family: inherit; cursor: pointer; white-space: nowrap; }
input { font-family: inherit; }
i { display: inline-flex; align-items: center; justify-content: center; }

.ambient {
  position: absolute;
  border-radius: 999px;
  pointer-events: none;
  filter: blur(10px);
  opacity: 0.9;
}
.ambient-a {
  width: 280px; height: 280px; top: -90px; left: -80px;
  background: radial-gradient(circle, rgba(119,148,46,0.18) 0%, rgba(119,148,46,0) 72%);
}
.ambient-b {
  width: 360px; height: 360px; right: -140px; top: 18%;
  background: radial-gradient(circle, rgba(182,199,122,0.18) 0%, rgba(182,199,122,0) 72%);
}
.ambient-c {
  width: 300px; height: 300px; left: 20%; bottom: -120px;
  background: radial-gradient(circle, rgba(100,115,30,0.12) 0%, rgba(100,115,30,0) 70%);
}

/* ═══════════════════════════ Main Content ═══════════════════════════ */
.main-content {
  min-height: 100vh;
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 40px 24px;
  position: relative;
  z-index: 1;
}

.form-wrapper {
  display: flex; gap: 20px; align-items: flex-start;
  max-width: 980px; width: 100%;
}

/* ═══════════════════════════ Card ═══════════════════════════ */
.card {
  background: var(--c-bg-card); border: 1px solid var(--c-border-light);
  border-radius: 14px; padding: 24px; transition: background 0.3s, border 0.3s;
}
.card-glow {
  position: relative; overflow: hidden;
}
.card-glow::before {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(ellipse at 50% 0%, rgba(119,148,46,0.08) 0%, transparent 70%);
}

/* ═══════════════════════════ Form Card ═══════════════════════════ */
.form-card { flex: 1; padding: 0; }

.form-header {
  display: flex; align-items: center; gap: 12px; padding: 22px 24px 18px;
}
.form-header-icon {
  width: 40px; height: 40px; border-radius: 12px;
  background: var(--c-accent-soft); display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.form-header-icon i { color: var(--c-accent-hover); font-size: 18px; }
.form-title { font-size: 16px; font-weight: 700; color: var(--c-text); }
.form-desc {
  font-size: 12px; color: var(--c-text-muted); margin-top: 2px;
  display: flex; align-items: center; gap: 4px;
}
.form-desc i { font-size: 13px; color: var(--c-amber); }
.warn-desc { color: var(--c-amber) !important; }

.form-divider {
  height: 1px; background: var(--c-border-light); margin: 0 24px;
}

.form-body { padding: 20px 24px 24px; display: flex; flex-direction: column; gap: 16px; }

/* ═══════════════════════════ Field ═══════════════════════════ */
.field-group { display: flex; flex-direction: column; gap: 6px; }
.field-label {
  font-size: 12px; font-weight: 600; color: var(--c-text-secondary);
  display: flex; align-items: center; gap: 5px;
}
.field-label i { font-size: 13px; color: var(--c-text-muted); }

.field-input-wrap {
  position: relative; display: flex; align-items: center;
}
.field-input {
  width: 100%; padding: 10px 14px; padding-right: 40px;
  border-radius: 10px; border: 1px solid var(--c-border);
  background: var(--c-bg-elevated); color: var(--c-text);
  font-size: 13px; outline: none; transition: all 0.2s;
}
.field-input::placeholder { color: var(--c-text-muted); }
.field-input:focus { border-color: var(--c-accent-border); box-shadow: 0 0 0 3px rgba(119,148,46,0.12); }

.field-toggle {
  position: absolute; right: 8px; top: 50%; transform: translateY(-50%);
  width: 30px; height: 30px; border-radius: 6px; border: none;
  background: transparent; display: flex; align-items: center; justify-content: center;
  color: var(--c-text-muted); transition: all 0.15s;
}
.field-toggle:hover { background: var(--c-border); color: var(--c-text-secondary); }
.field-toggle i { font-size: 15px; }

.field-hint {
  font-size: 11px; font-weight: 500; display: flex; align-items: center; gap: 4px;
}
.field-hint-error { color: var(--c-red); }
.field-hint-ok { color: var(--c-green); }

/* ═══════════════════════════ Password Strength ═══════════════════════════ */
.pw-strength {
  display: flex; align-items: center; gap: 10px; margin-top: 2px;
}
.pw-strength-bar {
  flex: 1; height: 4px; border-radius: 999px;
  background: var(--c-bg-elevated); overflow: hidden;
}
.pw-strength-fill {
  height: 100%; border-radius: 999px; transition: width 0.3s ease;
}
.pw-strength-weak { width: 25%; background: var(--c-red); }
.pw-strength-medium { width: 60%; background: var(--c-amber); }
.pw-strength-strong { width: 100%; background: var(--c-green); }

.pw-strength-text {
  font-size: 11px; font-weight: 600; min-width: 32px; text-align: right;
}
.pw-strength-text-weak { color: var(--c-red); }
.pw-strength-text-medium { color: var(--c-amber); }
.pw-strength-text-strong { color: var(--c-green); }

/* ═══════════════════════════ Error / Success ═══════════════════════════ */
.error-box {
  display: flex; align-items: flex-start; gap: 8px; padding: 12px;
  border-radius: 10px; background: var(--c-red-soft); border: 1px solid rgba(239,68,68,0.2);
}
.error-box i { color: var(--c-red); font-size: 14px; margin-top: 1px; flex-shrink: 0; }
.error-box p { font-size: 12px; color: var(--c-red); line-height: 1.5; }

.success-box {
  display: flex; align-items: center; gap: 8px; padding: 12px;
  border-radius: 10px; background: var(--c-green-soft); border: 1px solid rgba(34,197,94,0.2);
}
.success-box i { color: var(--c-green); font-size: 15px; flex-shrink: 0; }
.success-box p { font-size: 12px; color: var(--c-green); font-weight: 500; }

/* ═══════════════════════════ Buttons ═══════════════════════════ */
.btn-submit {
  width: 100%; padding: 11px; border-radius: 10px; border: none;
  background: var(--c-accent); color: #fff; font-size: 14px; font-weight: 600;
  transition: all 0.2s;
}
.btn-submit:hover:not(:disabled) { background: var(--c-accent-hover); }
.btn-submit:disabled { opacity: 0.4; cursor: not-allowed; }

.btn-back {
  width: 100%; padding: 9px; border-radius: 10px;
  border: 1px solid var(--c-border); background: var(--c-bg-card);
  color: var(--c-text-secondary); font-size: 13px; font-weight: 500;
  display: flex; align-items: center; justify-content: center; gap: 4px;
  transition: all 0.2s;
}
.btn-back:hover { background: var(--c-bg-elevated); color: var(--c-text); }
.btn-back i { font-size: 14px; }

/* ═══════════════════════════ Spinner ═══════════════════════════ */
.spinner-text { display: flex; align-items: center; justify-content: center; gap: 6px; }
.spinner {
  display: inline-block; width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
.spinner-light-sm { width: 14px; height: 14px; border-width: 2px; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ═══════════════════════════ Password Hint Card ═══════════════════════════ */
.pw-hint-card {
  width: 260px; flex-shrink: 0; padding: 20px; backdrop-filter: blur(10px);
}
.pw-hint-title {
  font-size: 12px; font-weight: 600; color: var(--c-text-secondary);
  display: flex; align-items: center; gap: 5px; margin-bottom: 14px;
}
.pw-hint-title i { font-size: 13px; color: var(--c-text-muted); }

.pw-hint-list {
  list-style: none; display: flex; flex-direction: column; gap: 8px;
}
.pw-hint-list li {
  display: flex; align-items: center; gap: 8px;
  font-size: 12px; color: var(--c-text-muted); transition: color 0.2s;
}
.pw-hint-list li i { font-size: 13px; width: 16px; text-align: center; flex-shrink: 0; }
.pw-hint-ok { color: var(--c-green) !important; }
.pw-hint-ok i { color: var(--c-green); }

/* ═══════════════════════════ Responsive ═══════════════════════════ */
@media (max-width: 768px) {
  .form-wrapper {
    flex-direction: column; gap: 16px;
  }
  .pw-hint-card { width: 100%; }
}
</style>
