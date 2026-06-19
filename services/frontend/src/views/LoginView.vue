<template>
  <div class="login-wrapper">
    <!-- Left: Image Panel -->
    <div class="image-panel">
      <img
        src="https://readdy.ai/api/search-image?query=Clean%20bright%20modern%20security%20operations%20center%20with%20white%20walls%20and%20sleek%20monitors%20displaying%20CCTV%20feeds%2C%20soft%20natural%20daylight%20through%20large%20windows%2C%20minimalist%20Scandinavian%20office%20design%2C%20teal%20and%20emerald%20accent%20details%2C%20airy%20spacious%20atmosphere%2C%20professional%20tech%20environment%20with%20potted%20plants%2C%20calming%20organized%20workspace%20with%20geometric%20glass%20partitions%2C%20soft%20diffused%20lighting%2C%20high-end%20corporate%20aesthetic&width=1920&height=1080&seq=cctv-login-hero-light-2026&orientation=landscape"
        alt="CCTV Security Operations Center"
        class="bg-img"
      />
      <!-- Dark overlay for text readability -->
      <div class="img-dark"></div>
      <!-- Right-fade gradient (image → white) -->
      <div class="img-fade"></div>

      <!-- Brand content over image -->
      <div class="brand-content">
        <div class="logo-wrap">
          <img
            src="https://public.readdy.ai/ai/img_res/82173d7e-de6c-4f3b-8df5-2f4c2501055a.png"
            alt="SIREN"
            class="brand-logo"
          />
        </div>
        <p class="brand-sub">AI 기반 지능형 영상 관제 솔루션</p>

        <div class="feature-list">
          <div class="feature-item">
            <div class="feature-icon">
              <i class="ri-eye-2-line"></i>
            </div>
            <span>실시간 VLM 위험 탐지</span>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <i class="ri-alarm-warning-line"></i>
            </div>
            <span>즉시 알림 및 대응</span>
          </div>
          <div class="feature-item">
            <div class="feature-icon">
              <i class="ri-shield-check-line"></i>
            </div>
            <span>24/7 무중단 모니터링</span>
          </div>
        </div>
      </div>
    </div>

    <!-- Right: Login Panel -->
    <div class="login-panel">
      <div class="login-card">
        <div class="card-header">
          <img
            class="card-logo"
            src="https://public.readdy.ai/ai/img_res/82173d7e-de6c-4f3b-8df5-2f4c2501055a.png"
            alt="SIREN"
          />
          <p class="secure-notice">보안 시스템 — 인가된 사용자만 접근 가능합니다</p>
        </div>

        <form @submit.prevent="handleLogin" class="login-form">
          <div class="form-group">
            <label for="username">아이디</label>
            <div class="input-wrapper">
              <div class="input-icon"><i class="ri-user-line"></i></div>
              <input
                id="username"
                v-model="username"
                type="text"
                autocomplete="username"
                placeholder="아이디를 입력하세요"
              />
            </div>
          </div>

          <div class="form-group">
            <label for="password">비밀번호</label>
            <div class="input-wrapper">
              <div class="input-icon"><i class="ri-lock-line"></i></div>
              <input
                id="password"
                v-model="password"
                :type="showPassword ? 'text' : 'password'"
                autocomplete="current-password"
                placeholder="비밀번호를 입력하세요"
              />
              <button type="button" class="toggle-password" @click="showPassword = !showPassword" tabindex="-1">
                <i :class="showPassword ? 'ri-eye-off-line' : 'ri-eye-line'"></i>
              </button>
            </div>
          </div>

          <div v-if="errorMsg" class="error-box">
            <i class="ri-error-warning-line"></i>
            <p>{{ errorMsg }}</p>
          </div>

          <button type="submit" :disabled="loading" class="submit-btn">
            <template v-if="loading">
              <svg class="spinner" viewBox="0 0 24 24" fill="none">
                <circle cx="12" cy="12" r="10" stroke="currentColor" stroke-width="3" fill="none" stroke-opacity="0.25" />
                <path fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
              </svg>
              <span>로그인 중...</span>
            </template>
            <template v-else>
              <span>로그인</span>
              <i class="ri-arrow-right-line"></i>
            </template>
          </button>

          <p class="forgot-text">
            비밀번호를 잊으셨나요?
            <a href="#" @click.prevent>관리자에게 문의하세요</a>
          </p>
        </form>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useAuthStore } from '../stores/authStore.js'

const router = useRouter()
const auth = useAuthStore()

const username = ref('')
const password = ref('')
const loading = ref(false)
const errorMsg = ref('')
const showPassword = ref(false)

async function handleLogin() {
  if (!username.value || !password.value) {
    errorMsg.value = '아이디와 비밀번호를 입력해주세요'
    return
  }
  loading.value = true
  errorMsg.value = ''
  try {
    await auth.login(username.value, password.value)
    router.replace('/')
  } catch (e) {
    errorMsg.value = e.response?.data?.detail || '로그인에 실패했습니다'
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
* { box-sizing: border-box; margin: 0; padding: 0; }

.login-wrapper {
  --c-accent: #77942e;
  --c-accent-soft: #eef2df;
  --c-accent-border: #b6c77a;
  --c-accent-hover: #64731e;
  --c-bg-dark: #0b0e06;
  --c-bg-dark-elevated: #14180d;
  --c-text-muted: #8f9683;
  --c-panel-border: rgba(182, 199, 122, 0.16);
  --c-panel-shadow: rgba(11, 14, 6, 0.34);
  display: flex;
  min-height: 100vh;
  font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
  background:
    radial-gradient(circle at 78% 16%, rgba(119, 148, 46, 0.14), transparent 20%),
    linear-gradient(135deg, #070904 0%, var(--c-bg-dark) 42%, #101508 100%);
}

/* ── Left image panel ── */
.image-panel {
  position: relative;
  width: 60%;
  flex-shrink: 0;
  overflow: hidden;
}

.bg-img {
  position: absolute;
  inset: 0;
  width: 100%;
  height: 100%;
  object-fit: cover;
  object-position: center;
  transform: scale(1.03);
}

/* Dark tint for text readability */
.img-dark {
  position: absolute;
  inset: 0;
  background: linear-gradient(
    to right,
    rgba(10, 14, 7, 0.66) 0%,
    rgba(10, 14, 7, 0.34) 48%,
    rgba(10, 14, 7, 0.12) 100%
  );
  z-index: 1;
}

/* Fade image → dark background toward the right edge */
.img-fade {
  position: absolute;
  top: 0;
  right: 0;
  bottom: 0;
  width: 42%;
  background: linear-gradient(
    to right,
    rgba(11, 14, 6, 0) 0%,
    rgba(11, 14, 6, 0.08) 24%,
    rgba(11, 14, 6, 0.24) 48%,
    rgba(11, 14, 6, 0.56) 72%,
    rgba(11, 14, 6, 0.84) 88%,
    rgba(11, 14, 6, 1) 100%
  );
  z-index: 2;
}

/* Brand content overlay */
.brand-content {
  position: absolute;
  inset: 0;
  z-index: 3;
  display: flex;
  flex-direction: column;
  justify-content: center;
  padding: 56px 52px 56px 140px;
}

.brand-content::before {
  content: '';
  position: absolute;
  left: 84px;
  top: 50%;
  width: min(560px, calc(100% - 136px));
  height: 440px;
  transform: translateY(-50%);
  border-radius: 36px;
  background:
    radial-gradient(circle at 24% 28%, rgba(11, 14, 6, 0.50) 0%, rgba(11, 14, 6, 0.34) 34%, rgba(11, 14, 6, 0.16) 62%, rgba(11, 14, 6, 0) 100%),
    linear-gradient(90deg, rgba(11, 14, 6, 0.42) 0%, rgba(11, 14, 6, 0.22) 46%, rgba(11, 14, 6, 0) 100%);
  filter: blur(8px);
  z-index: -1;
}

.logo-wrap { margin-bottom: 24px; }

.brand-logo {
  height: 64px;
  object-fit: contain;
  filter: brightness(0) invert(1);
  filter: brightness(0) invert(1) drop-shadow(0 10px 24px rgba(0, 0, 0, 0.28));
}

.brand-sub {
  font-size: 16px;
  color: rgba(255, 255, 255, 0.76);
  margin-bottom: 44px;
  text-shadow: 0 2px 12px rgba(0, 0, 0, 0.34);
}

.feature-list {
  display: flex;
  flex-direction: column;
  gap: 20px;
}

.feature-item {
  display: flex;
  align-items: center;
  gap: 14px;
  color: rgba(255, 255, 255, 0.90);
  font-size: 15px;
  font-weight: 500;
  text-shadow: 0 2px 10px rgba(0, 0, 0, 0.32);
}

.feature-icon {
  width: 40px;
  height: 40px;
  border-radius: 12px;
  background: rgba(119, 148, 46, 0.18);
  border: 1px solid rgba(182, 199, 122, 0.32);
  display: flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
  backdrop-filter: blur(8px);
}

.feature-icon i {
  color: #dbe8b2;
  font-size: 18px;
}

/* ── Right login panel ── */
.login-panel {
  flex: 1;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 48px 40px;
  background:
    radial-gradient(circle at top left, rgba(119, 148, 46, 0.18), transparent 30%),
    radial-gradient(circle at bottom right, rgba(119, 148, 46, 0.08), transparent 24%),
    linear-gradient(180deg, var(--c-bg-dark) 0%, var(--c-bg-dark-elevated) 100%);
}

.login-card {
  width: 100%;
  max-width: 400px;
  background: rgba(255, 255, 255, 0.96);
  border-radius: 20px;
  border: 1px solid rgba(182, 199, 122, 0.2);
  padding: 36px;
  box-shadow:
    0 24px 60px var(--c-panel-shadow),
    0 0 0 1px rgba(255, 255, 255, 0.22) inset;
}

.card-header {
  text-align: center;
  margin-bottom: 28px;
}

.card-logo {
  height: 32px;
  margin: 0 auto 12px;
  object-fit: contain;
}

.secure-notice {
  font-size: 12px;
  color: #76806a;
}

.login-form {
  display: flex;
  flex-direction: column;
  gap: 18px;
}

.form-group label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: #243010;
  margin-bottom: 6px;
}

.input-wrapper { position: relative; }

.input-icon {
  position: absolute;
  top: 0; bottom: 0; left: 0;
  padding-left: 14px;
  display: flex;
  align-items: center;
  pointer-events: none;
}

.input-icon i { color: #94a3b8; font-size: 15px; }

.input-wrapper input {
  width: 100%;
  background: #f7f8f2;
  border: 1px solid #d9e1c3;
  border-radius: 12px;
  padding: 12px 16px 12px 40px;
  font-size: 14px;
  color: #0f172a;
  outline: none;
  transition: all 0.2s ease;
}

.input-wrapper input::placeholder { color: #94a3b8; }

.input-wrapper input:focus {
  border-color: var(--c-accent);
  box-shadow: 0 0 0 3px rgba(119, 148, 46, 0.14);
  background: #ffffff;
}

.input-wrapper input[type="password"] { padding-right: 44px; }

.toggle-password {
  position: absolute;
  top: 0; bottom: 0; right: 0;
  padding-right: 14px;
  display: flex;
  align-items: center;
  background: none;
  border: none;
  color: #94a3b8;
  cursor: pointer;
  transition: color 0.2s;
}

.toggle-password:hover { color: #475569; }
.toggle-password i { font-size: 15px; }

.error-box {
  display: flex;
  align-items: center;
  gap: 8px;
  background: rgba(239, 68, 68, 0.10);
  border: 1px solid rgba(239, 68, 68, 0.35);
  border-radius: 10px;
  padding: 10px 14px;
}

.error-box i { color: #ef4444; font-size: 15px; flex-shrink: 0; }
.error-box p { color: #ef4444; font-size: 12px; }

.submit-btn {
  width: 100%;
  background: linear-gradient(135deg, #7d9930 0%, var(--c-accent) 100%);
  color: #ffffff;
  font-weight: 600;
  font-size: 14px;
  border: none;
  border-radius: 12px;
  padding: 13px;
  cursor: pointer;
  transition: all 0.2s ease;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  box-shadow: 0 12px 24px rgba(119, 148, 46, 0.22);
}

.submit-btn:hover {
  background: linear-gradient(135deg, #6c8427 0%, var(--c-accent-hover) 100%);
  box-shadow: 0 16px 28px rgba(100, 115, 30, 0.24);
}
.submit-btn:disabled { background: #d9e3b8; color: rgba(53, 67, 18, 0.55); box-shadow: none; cursor: not-allowed; }
.submit-btn:active:not(:disabled) { transform: scale(0.98); }

.spinner {
  width: 16px;
  height: 16px;
  animation: spin 1s linear infinite;
}

@keyframes spin { from { transform: rotate(0deg); } to { transform: rotate(360deg); } }

.forgot-text { text-align: center; font-size: 13px; color: #64748b; }

.forgot-text a {
  color: var(--c-accent);
  text-decoration: none;
  font-weight: 500;
  transition: color 0.2s;
}

.forgot-text a:hover { color: var(--c-accent-hover); }

/* ── Responsive: mobile shows only login panel ── */
@media (max-width: 1023px) {
  .image-panel { display: none; }
  .login-panel { padding: 32px 24px; }
}
</style>
