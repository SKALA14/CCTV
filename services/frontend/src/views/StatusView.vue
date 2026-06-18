<template>
  <div class="app-shell" :class="{ dark: isDark }">
    <!-- Top Navigation -->
    <header class="topnav">
      <div class="topnav-inner">
        <div class="topnav-actions topnav-actions-only">
          <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '라이트 모드' : '다크 모드'">
            <i :class="isDark ? 'ri-sun-line' : 'ri-moon-line'"></i>
          </button>
          <router-link to="/profile" class="profile-nav-btn">
            <i class="ri-user-3-line"></i>
          </router-link>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Page Header -->
      <div class="page-header">
        <div class="page-header-icon">
          <i class="ri-dashboard-line"></i>
        </div>
        <div>
          <h1 class="page-title">System Status</h1>
          <p class="page-desc">구역 요약, CCTV 장비 상태, 계정 정보를 한눈에 확인할 수 있습니다.</p>
        </div>
        <!-- Refresh button -->
        <button class="btn-refresh" @click="refreshAll" :disabled="refreshing">
          <i :class="refreshing ? 'ri-loader-4-line spin-icon' : 'ri-refresh-line'"></i>
          <span>{{ refreshing ? '새로고침 중...' : '새로고침' }}</span>
        </button>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="loading-center">
        <span class="spinner spinner-accent"></span>
        <p>시스템 현황을 불러오는 중...</p>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="error-box">
        <i class="ri-error-warning-line"></i>
        <div>
          <p class="error-title">시스템 현황을 불러오지 못했습니다</p>
          <p class="error-detail">{{ error }}</p>
          <button class="btn-ghost" @click="loadAll">다시 시도</button>
        </div>
      </div>

      <!-- Main Content -->
      <template v-else>
        <!-- Section: Zone Overview -->
        <div class="section-header">
          <h2 class="section-title">
            <i class="ri-map-pin-line"></i> 구역별 요약
          </h2>
          <span class="section-badge">{{ overview.length }} 구역</span>
        </div>

        <div v-if="overview.length" class="overview-grid">
          <div v-for="z in overview" :key="z.zone" class="card card-glow overview-card">
            <div class="overview-card-top">
              <div class="overview-zone-icon">
                <i class="ri-building-line"></i>
              </div>
              <div class="overview-zone-info">
                <p class="overview-zone-name">{{ z.zone }}</p>
                <p class="overview-zone-sub">
                  <span class="overview-stat">
                    <i class="ri-camera-line"></i>
                    <span class="overview-num">{{ z.camera_count }}</span>대
                  </span>
                </p>
              </div>
            </div>
            <div class="overview-divider"></div>
            <button class="overview-event-btn" @click="openZoneEvents(z)">
              <div class="overview-event-left">
                <i class="ri-flashlight-line"></i>
                <span>오늘 이벤트</span>
              </div>
              <div class="overview-event-right">
                <span class="overview-num">{{ z.today_event_count }}</span>
                <i class="ri-arrow-right-s-line"></i>
              </div>
            </button>
          </div>
        </div>
        <div v-else class="empty-mini">
          <i class="ri-inbox-line"></i>
          <span>등록된 채널이 없습니다</span>
        </div>

        <!-- Section: CCTV Device Status -->
        <div class="section-header section-header-gap">
          <h2 class="section-title">
            <i class="ri-camera-line"></i> CCTV 기기 상태
          </h2>
          <div class="status-summary">
            <span class="status-dot status-dot-online"></span>
            <span class="status-summary-text">온라인: {{ onlineCount }}</span>
            <span class="status-dot status-dot-offline"></span>
            <span class="status-summary-text">오프라인: {{ offlineCount }}</span>
          </div>
        </div>

        <div class="card card-glow table-card">
          <div v-if="devices.length" class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th class="th-zone">구역</th>
                  <th class="th-cam">카메라</th>
                  <th class="th-src">소스</th>
                  <th class="th-status">상태</th>
                  <th class="th-seen">마지막 수신</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(d, i) in devices" :key="i">
                  <td class="td-muted">{{ d.zone }}</td>
                  <td class="td-main">{{ d.camera_name }}</td>
                  <td class="td-muted">{{ d.source_type }}</td>
                  <td>
                    <span class="device-status" :class="d.online ? 'device-online' : 'device-offline'">
                      <span class="device-status-dot"></span>
                      {{ d.online ? '온라인' : '오프라인' }}
                    </span>
                  </td>
                  <td class="td-muted td-mono">{{ fmt(d.last_seen) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty-mini">
            <i class="ri-camera-off-line"></i>
            <span>등록된 카메라가 없습니다</span>
          </div>
        </div>

        <!-- Section: Account Status -->
        <div class="section-header section-header-gap">
          <h2 class="section-title">
            <i class="ri-user-settings-line"></i> 계정 현황
          </h2>
          <span class="section-badge">{{ accounts.length }}명</span>
        </div>

        <div class="card card-glow table-card">
          <div v-if="accounts.length" class="table-wrap">
            <table class="data-table">
              <thead>
                <tr>
                  <th class="th-zone">username</th>
                  <th class="th-cam">role</th>
                  <th class="th-seen">마지막 로그인</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="(a, i) in accounts" :key="i">
                  <td class="td-main">
                    {{ a.username }}
                    <span v-if="a.must_change_password" class="initial-badge">(초기)</span>
                  </td>
                  <td>
                    <span class="role-chip" :class="'role-' + a.role">{{ a.role }}</span>
                  </td>
                  <td class="td-muted td-mono">{{ fmt(a.last_login) }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div v-else class="empty-mini">
            <i class="ri-user-line"></i>
            <span>등록된 계정이 없습니다</span>
          </div>
        </div>
      </template>
    </main>

    <!-- Zone Today Events Modal -->
    <Teleport to="body">
      <div
        v-if="eventsModal.open"
        class="modal-overlay"
        @click.self="eventsModal.open = false"
      >
        <div class="modal-panel">
          <div class="modal-header">
            <div class="modal-header-left">
              <div class="modal-header-icon">
                <i class="ri-flashlight-line"></i>
              </div>
              <div>
                <h3 class="modal-title">{{ eventsModal.zone }}</h3>
                <p class="modal-sub">오늘 이벤트</p>
              </div>
            </div>
            <button class="modal-close" @click="eventsModal.open = false">
              <i class="ri-close-line"></i>
            </button>
          </div>

          <div class="modal-body">
            <!-- Loading -->
            <div v-if="eventsModal.loading" class="loading-center">
              <span class="spinner spinner-accent spinner-sm"></span>
              <p>이벤트 불러오는 중...</p>
            </div>

            <!-- Empty -->
            <div v-else-if="!eventsModal.events.length" class="empty-mini empty-mini-lg">
              <i class="ri-check-double-line"></i>
              <span>오늘 발생한 이벤트가 없습니다</span>
              <p class="empty-mini-hint">이상 없음</p>
            </div>

            <!-- Events Table -->
            <div v-else class="table-wrap">
              <table class="data-table">
                <thead>
                  <tr>
                    <th class="th-seen">시간</th>
                    <th class="th-cam">카메라</th>
                    <th class="th-src">유형</th>
                    <th class="th-status">위험도</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="e in eventsModal.events" :key="e.event_id">
                    <td class="td-muted td-mono">{{ fmtTime(e.occurred_at) }}</td>
                    <td class="td-main">{{ e.camera_name }}</td>
                    <td class="td-main">{{ e.event_type }}</td>
                    <td>
                      <span class="danger-badge" :class="'danger-' + e.danger_level">
                        {{ dangerLabels[e.danger_level] || e.danger_level }}
                      </span>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>
          </div>

          <div class="modal-footer">
            <span class="modal-footer-hint">{{ eventsModal.events.length }}건</span>
            <button class="btn-ghost" @click="eventsModal.open = false">닫기</button>
          </div>
        </div>
      </div>
    </Teleport>
  </div>
</template>

<script>
export default { name: 'StatusView' }
</script>

<script setup>
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { useTheme } from '../composables/useTheme.js'
import { getOverview, getDevices, getAccounts, getTodayEvents } from '../api/status.js'

/* ── Theme ── */
const { isDark, toggle: toggleTheme } = useTheme()

/* ── State ── */
const loading = ref(false)
const error = ref('')
const refreshing = ref(false)
const overview = ref([])
const devices = ref([])
const accounts = ref([])
let timer = null

const dangerLabels = { critical: '심각', high: '높음', low: '낮음', info: '정보' }

const eventsModal = ref({ open: false, loading: false, zone: '', events: [] })

/* ── Computed ── */
const onlineCount = computed(() => devices.value.filter(d => d.online).length)
const offlineCount = computed(() => devices.value.filter(d => !d.online).length)

/* ── Formatters ── */
function fmt(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getMonth() + 1)}/${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

function fmtTime(iso) {
  if (!iso) return '—'
  const d = new Date(iso)
  const pad = (n) => String(n).padStart(2, '0')
  return `${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
}

/* ── Methods ── */
async function loadAll() {
  loading.value = true
  error.value = ''
  try {
    const [ov, dv, ac] = await Promise.all([getOverview(), getDevices(), getAccounts()])
    overview.value = ov
    devices.value = dv
    accounts.value = ac
  } catch (e) {
    error.value = e.response?.data?.detail ?? e.message ?? 'An error occurred while loading data.'
  } finally {
    loading.value = false
  }
}

async function refreshAll() {
  if (refreshing.value) return
  refreshing.value = true
  try {
    const [ov, dv] = await Promise.all([getOverview(), getDevices()])
    overview.value = ov
    devices.value = dv
  } catch {
    // silent — keep existing data on refresh failure
  } finally {
    refreshing.value = false
  }
}

async function openZoneEvents(z) {
  eventsModal.value = { open: true, loading: true, zone: z.zone, events: [] }
  try {
    eventsModal.value.events = await getTodayEvents(z.zone)
  } catch {
    eventsModal.value.events = []
  } finally {
    eventsModal.value.loading = false
  }
}

/* ── Lifecycle ── */
onMounted(() => {
  loadAll()
  timer = setInterval(refreshAll, 30000)
})
onUnmounted(() => {
  if (timer) clearInterval(timer)
})
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
  --c-orange-soft: #fff7ed;
  --c-blue-soft: #eff6ff;
  --c-blue-text: #3b82f6;
}

.app-shell.dark {
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
  --c-orange-soft: #2d1a10;
  --c-blue-soft: #1a2540;
}

/* ═══════════════════════════ Base ═══════════════════════════ */
.app-shell {
  min-height: 100vh;
  background: var(--c-bg);
  color: var(--c-text);
  font-family: 'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  transition: background 0.3s, color 0.3s;
  -webkit-font-smoothing: antialiased;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

button { font-family: inherit; cursor: pointer; white-space: nowrap; }
input, textarea { font-family: inherit; }
i { display: inline-flex; align-items: center; justify-content: center; }

/* ═══════════════════════════ Top Nav ═══════════════════════════ */
.topnav {
  position: sticky; top: 0; z-index: 50;
  background: var(--c-bg-card);
  border-bottom: 1px solid var(--c-border-light);
  backdrop-filter: blur(12px);
}
.topnav-inner {
  max-width: 1440px; margin: 0 auto; padding: 0 24px;
  min-height: 64px; display: flex; align-items: center; justify-content: space-between;
}
.topnav-brand { display: flex; align-items: center; gap: 8px; }
.brand-logo-icon { height: 30px; object-fit: contain; }
.brand-logo-text { height: 20px; object-fit: contain; }
.profile-nav-btn {
  display: flex; align-items: center; justify-content: center;
  width: 40px; height: 40px; border-radius: 50%;
  color: var(--c-accent-hover); text-decoration: none;
  background: var(--c-accent-soft);
  border: 1px solid var(--c-accent-border);
  box-shadow: 0 4px 12px rgba(17, 24, 39, 0.06);
  transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
}
.profile-nav-btn:hover { transform: translateY(-1px); background: color-mix(in srgb, var(--c-accent-soft) 78%, white); box-shadow: 0 8px 18px rgba(17, 24, 39, 0.08); }
.profile-nav-btn i { font-size: 18px; }
.brand-icon {
  width: 32px; height: 32px; border-radius: 10px;
  background: var(--c-accent); display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.brand-icon i { color: #fff; font-size: 16px; }
.brand-text { display: flex; flex-direction: column; }
.brand-title { font-size: 13px; font-weight: 700; color: var(--c-text); line-height: 1; }
.brand-sub { font-size: 10px; color: var(--c-text-muted); line-height: 1; margin-top: 1px; }

.topnav-actions { display: flex; align-items: center; gap: 12px; }
.topnav-actions-only { margin-left: auto; }
.topnav-links { display: flex; gap: 4px; }
.nav-link {
  font-size: 12px; padding: 6px 12px; border-radius: 8px;
  color: var(--c-text-secondary); text-decoration: none; font-weight: 500;
  transition: all 0.15s;
}
.nav-link:hover { color: var(--c-text); background: var(--c-bg-elevated); }
.nav-link.active { background: var(--c-accent-soft); color: var(--c-accent-hover); font-weight: 600; }
.nav-divider { width: 1px; height: 20px; background: var(--c-border); }

.theme-toggle {
  width: 40px; height: 40px; border-radius: 10px; border: 1px solid var(--c-border);
  background: var(--c-bg-elevated); display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.theme-toggle:hover { background: var(--c-border); }
.theme-toggle i { font-size: 18px; color: var(--c-text-secondary); }

/* ═══════════════════════════ Main Content ═══════════════════════════ */
.main-content { max-width: 1440px; margin: 0 auto; padding: 24px; }

.page-header { display: flex; align-items: center; gap: 8px; margin-bottom: 20px; }
.page-header-icon {
  width: 28px; height: 28px; border-radius: 8px;
  background: var(--c-accent-soft); display: flex; align-items: center; justify-content: center;
}
.page-header-icon i { color: var(--c-accent-hover); font-size: 14px; }
.page-title { font-size: 18px; font-weight: 700; color: var(--c-text); }
.page-desc { font-size: 12px; color: var(--c-text-muted); margin-left: 8px; }

/* Refresh Button */
.btn-refresh {
  display: flex; align-items: center; gap: 5px; margin-left: auto;
  font-size: 12px; padding: 6px 14px; border-radius: 8px;
  border: 1px solid var(--c-border); background: var(--c-bg-card);
  color: var(--c-text-secondary); font-weight: 500;
  transition: all 0.2s;
}
.btn-refresh:hover:not(:disabled) { background: var(--c-bg-elevated); color: var(--c-text); }
.btn-refresh:disabled { opacity: 0.5; cursor: not-allowed; }
.btn-refresh i { font-size: 13px; }
.spin-icon { animation: spin 0.8s linear infinite; }

/* ═══════════════════════════ Section Header ═══════════════════════════ */
.section-header {
  display: flex; align-items: center; gap: 10px; margin-bottom: 14px;
}
.section-header-gap { margin-top: 28px; }
.section-title {
  font-size: 14px; font-weight: 600; color: var(--c-text);
  display: flex; align-items: center; gap: 6px;
}
.section-title i { color: var(--c-accent-hover); font-size: 14px; }
.section-badge {
  font-size: 11px; padding: 3px 10px; border-radius: 999px;
  background: var(--c-bg-elevated); color: var(--c-text-secondary);
  border: 1px solid var(--c-border); font-weight: 500;
}

/* Status Summary */
.status-summary {
  display: flex; align-items: center; gap: 6px; margin-left: auto;
  font-size: 11px;
}
.status-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
}
.status-dot-online { background: var(--c-green); box-shadow: 0 0 6px rgba(34,197,94,0.4); }
.status-dot-offline { background: var(--c-text-muted); }
.status-summary-text { color: var(--c-text-secondary); font-weight: 500; }

/* ═══════════════════════════ Card ═══════════════════════════ */
.card {
  background: var(--c-bg-card); border: 1px solid var(--c-border-light);
  border-radius: 14px; padding: 20px; transition: background 0.3s, border 0.3s;
}
.card-glow {
  position: relative; overflow: hidden;
}
.card-glow::before {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(ellipse at 50% 0%, rgba(132,204,22,0.05) 0%, transparent 70%);
}
.table-card { padding: 0; overflow: hidden; }

/* ═══════════════════════════ Overview Cards Grid ═══════════════════════════ */
.overview-grid {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 0;
}

.overview-card {
  padding: 0; display: flex; flex-direction: column;
}

.overview-card-top {
  display: flex; align-items: center; gap: 10px; padding: 16px 18px 14px;
}
.overview-zone-icon {
  width: 36px; height: 36px; border-radius: 10px;
  background: var(--c-accent-soft); display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.overview-zone-icon i { color: var(--c-accent-hover); font-size: 16px; }
.overview-zone-info { display: flex; flex-direction: column; gap: 2px; }
.overview-zone-name { font-size: 13px; font-weight: 600; color: var(--c-text); }
.overview-zone-sub { font-size: 11px; color: var(--c-text-muted); }
.overview-stat {
  display: flex; align-items: center; gap: 4px;
}
.overview-stat i { font-size: 11px; }
.overview-num {
  font-family: 'JetBrains Mono', monospace; font-weight: 600; color: var(--c-text-secondary);
}

.overview-divider {
  height: 1px; background: var(--c-border-light); margin: 0 18px;
}

.overview-event-btn {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 18px; border: none; background: none; width: 100%;
  transition: background 0.15s;
}
.overview-event-btn:hover { background: var(--c-bg-elevated); }
.overview-event-left {
  display: flex; align-items: center; gap: 6px;
  font-size: 12px; color: var(--c-text-secondary); font-weight: 500;
}
.overview-event-left i { font-size: 13px; color: var(--c-amber); }
.overview-event-right {
  display: flex; align-items: center; gap: 4px;
  font-size: 12px; color: var(--c-text-secondary); font-weight: 500;
}
.overview-event-right i { font-size: 14px; color: var(--c-text-muted); }

/* ═══════════════════════════ Data Table ═══════════════════════════ */
.table-wrap { overflow-x: auto; }
.data-table {
  width: 100%; border-collapse: collapse; font-size: 13px;
}
.data-table thead tr {
  background: var(--c-bg-elevated);
}
.data-table th {
  text-align: left; padding: 10px 16px;
  font-size: 11px; font-weight: 600; color: var(--c-text-muted);
  text-transform: uppercase; letter-spacing: 0.04em; white-space: nowrap;
}
.data-table tbody tr {
  border-top: 1px solid var(--c-border-light);
  transition: background 0.15s;
}
.data-table tbody tr:hover { background: var(--c-bg-elevated); }
.data-table td { padding: 10px 16px; }

.th-zone { width: 18%; }
.th-cam { width: 24%; }
.th-src { width: 16%; }
.th-status { width: 16%; }
.th-seen { width: 26%; }

.td-muted { color: var(--c-text-muted); }
.td-main { color: var(--c-text); font-weight: 500; }
.td-mono { font-family: 'JetBrains Mono', monospace; font-size: 12px; }

/* Device Status */
.device-status {
  display: inline-flex; align-items: center; gap: 6px;
  font-size: 12px; font-weight: 500;
}
.device-status-dot {
  width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0;
}
.device-online { color: var(--c-green); }
.device-online .device-status-dot { background: var(--c-green); box-shadow: 0 0 6px rgba(34,197,94,0.4); }
.device-offline { color: var(--c-text-muted); }
.device-offline .device-status-dot { background: var(--c-text-muted); }

/* Account Role */
.role-chip {
  display: inline-flex; padding: 3px 10px; border-radius: 6px;
  font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.04em;
}
.role-admin { background: var(--c-red-soft); color: var(--c-red); }
.role-operator { background: var(--c-amber-soft); color: var(--c-amber); }
.role-viewer { background: var(--c-blue-soft); color: var(--c-blue-text); }

.initial-badge {
  display: inline-flex; margin-left: 5px; padding: 1px 6px; border-radius: 4px;
  font-size: 10px; font-weight: 600; background: var(--c-amber-soft); color: var(--c-amber);
  vertical-align: middle;
}

/* ═══════════════════════════ Danger Badge ═══════════════════════════ */
.danger-badge {
  display: inline-flex; padding: 3px 10px; border-radius: 6px;
  font-size: 11px; font-weight: 600;
}
.danger-critical { background: var(--c-red-soft); color: var(--c-red); }
.danger-high { background: var(--c-orange-soft); color: var(--c-orange); }
.danger-low { background: var(--c-amber-soft); color: var(--c-amber); }
.danger-info { background: var(--c-blue-soft); color: var(--c-blue-text); }

/* ═══════════════════════════ Modal ═══════════════════════════ */
.modal-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,0.5); backdrop-filter: blur(4px);
  display: flex; align-items: center; justify-content: center; padding: 24px;
}
.modal-panel {
  width: 100%; max-width: 640px; max-height: 80vh;
  background: #ffffff; border: 1px solid #e5e7eb;
  border-radius: 16px; display: flex; flex-direction: column;
  box-shadow: 0 20px 60px rgba(0,0,0,0.15); overflow: hidden;
}

.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 18px 20px; flex-shrink: 0;
  border-bottom: 1px solid #f0f0f0;
}
.modal-header-left { display: flex; align-items: center; gap: 10px; }
.modal-header-icon {
  width: 34px; height: 34px; border-radius: 10px;
  background: var(--c-amber-soft); display: flex; align-items: center; justify-content: center;
}
.modal-header-icon i { color: var(--c-amber); font-size: 15px; }
.modal-title { font-size: 14px; font-weight: 600; color: #111827; }
.modal-sub { font-size: 11px; color: #9ca3af; margin-top: 1px; }

.modal-close {
  width: 32px; height: 32px; border-radius: 8px; border: 1px solid #e5e7eb;
  background: #f3f4f6; display: flex; align-items: center; justify-content: center;
  transition: all 0.15s;
}
.modal-close:hover { background: #e5e7eb; }
.modal-close i { font-size: 14px; color: #4b5563; }

.modal-body { flex: 1; overflow-y: auto; padding: 0; }
.modal-body .data-table thead { position: sticky; top: 0; z-index: 1; }

.modal-footer {
  display: flex; align-items: center; justify-content: space-between;
  padding: 12px 20px; flex-shrink: 0;
  border-top: 1px solid #f0f0f0;
}
.modal-footer-hint { font-size: 11px; color: #9ca3af; }

/* ═══════════════════════════ Buttons ═══════════════════════════ */
.btn-ghost {
  font-size: 12px; padding: 6px 14px; border-radius: 8px; border: 1px solid var(--c-border);
  background: var(--c-bg-elevated); color: var(--c-text-secondary);
  display: inline-flex; align-items: center; gap: 5px; transition: all 0.2s;
}
.btn-ghost:hover { background: var(--c-border); color: var(--c-text); }

/* ═══════════════════════════ Spinner ═══════════════════════════ */
.spinner-accent {
  display: inline-block; width: 32px; height: 32px;
  border: 3px solid var(--c-accent-soft); border-top-color: var(--c-accent);
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
.spinner-accent.spinner-sm { width: 24px; height: 24px; border-width: 2px; }
@keyframes spin { to { transform: rotate(360deg); } }

.loading-center {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 64px 0; gap: 12px;
}
.loading-center p { font-size: 12px; color: var(--c-text-muted); }

/* ═══════════════════════════ Empty / Error ═══════════════════════════ */
.empty-mini {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 32px 0; gap: 6px;
}
.empty-mini-lg { padding: 40px 0; }
.empty-mini i { font-size: 18px; color: var(--c-text-muted); }
.empty-mini span { font-size: 12px; color: var(--c-text-muted); }
.empty-mini-hint { font-size: 11px; color: var(--c-text-muted); margin-top: 2px; }

.error-box {
  display: flex; align-items: flex-start; gap: 12px; padding: 16px;
  border-radius: 12px; background: var(--c-red-soft); border: 1px solid rgba(239,68,68,0.2);
}
.error-box i { color: var(--c-red); font-size: 18px; margin-top: 1px; flex-shrink: 0; }
.error-title { font-size: 13px; font-weight: 600; color: var(--c-red); margin-bottom: 4px; }
.error-detail { font-size: 12px; color: var(--c-red); opacity: 0.8; margin-bottom: 8px; }

/* ═══════════════════════════ Scrollbar ═══════════════════════════ */
.modal-body::-webkit-scrollbar { width: 4px; }
.modal-body::-webkit-scrollbar-track { background: transparent; }
.modal-body::-webkit-scrollbar-thumb { background: var(--c-border); border-radius: 999px; }
.modal-body::-webkit-scrollbar-thumb:hover { background: var(--c-text-muted); }

/* ═══════════════════════════ Responsive ═══════════════════════════ */
@media (max-width: 1024px) {
  .topnav-links { display: none; }
  .nav-divider { display: none; }
  .page-desc { display: none; }
  .overview-grid { grid-template-columns: 1fr 1fr; }
}

@media (max-width: 640px) {
  .overview-grid { grid-template-columns: 1fr; }
  .page-header { flex-wrap: wrap; }
  .btn-refresh { margin-left: 0; }
  .section-header { flex-wrap: wrap; }
  .status-summary { margin-left: 0; }
}
</style>
