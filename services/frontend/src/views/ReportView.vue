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
          <i class="ri-bar-chart-line"></i>
        </div>
        <div>
          <h1 class="page-title">Safety Report</h1>
          <p class="page-desc">기간별 이벤트 수와 위험도 분포를 한눈에 확인할 수 있습니다.</p>
        </div>
        <!-- Period Selector -->
        <div class="period-pills">
          <button
            v-for="d in [7, 30]"
            :key="d"
            class="period-pill"
            :class="{ 'period-pill-active': days === d }"
            @click="onPeriodChange(d)"
          >
            최근 {{ d }}일
          </button>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="loading-center">
        <span class="spinner spinner-accent"></span>
        <p>리포트 데이터 불러오는 중...</p>
      </div>

      <!-- Error -->
      <div v-else-if="error" class="error-box">
        <i class="ri-error-warning-line"></i>
        <div>
          <p class="error-title">리포트를 불러오지 못했습니다</p>
          <p class="error-detail">{{ error }}</p>
          <button class="btn-ghost" @click="load">다시 시도</button>
        </div>
      </div>

      <!-- Report Content -->
      <template v-else-if="data">
        <!-- Overview Cards Row -->
        <div class="overview-row">
          <!-- Total Events -->
          <div class="card card-glow overview-card">
            <div class="overview-label">
              <i class="ri-flashlight-line"></i>
              <span>최근 {{ data.days }}일 이벤트</span>
            </div>
            <div class="overview-value">
              <span class="overview-number">{{ data.total.toLocaleString() }}</span>
              <span class="overview-unit">건</span>
            </div>
            <div class="overview-sub">
              <span v-if="data.trend > 0" class="trend-up">
                <i class="ri-arrow-up-line"></i> 전 기간 대비 {{ data.trend }}%
              </span>
              <span v-else-if="data.trend < 0" class="trend-down">
                <i class="ri-arrow-down-line"></i> 전 기간 대비 {{ Math.abs(data.trend) }}%
              </span>
              <span v-else class="trend-flat">
                <i class="ri-subtract-line"></i> 전 기간과 동일
              </span>
            </div>
          </div>

          <!-- Critical Events Count -->
          <div class="card card-glow overview-card overview-card-danger">
            <div class="overview-label">
              <i class="ri-alert-line"></i>
              <span>위험 이벤트</span>
            </div>
            <div class="overview-value">
              <span class="overview-number">{{ data.danger_breakdown.critical || 0 }}</span>
              <span class="overview-unit">건</span>
            </div>
            <div class="overview-sub">
              <span class="overview-sub-text">전체의 {{ criticalPct }}%</span>
            </div>
          </div>

          <!-- Avg per Day -->
          <div class="card card-glow overview-card">
            <div class="overview-label">
              <i class="ri-calendar-check-line"></i>
              <span>일 평균</span>
            </div>
            <div class="overview-value">
              <span class="overview-number">{{ avgPerDay }}</span>
              <span class="overview-unit">/일</span>
            </div>
            <div class="overview-sub">
              <span class="overview-sub-text">최고: {{ peakDay }}</span>
            </div>
          </div>
        </div>

        <!-- Charts Row 1 -->
        <div class="chart-row">
          <!-- Danger Distribution -->
          <div class="card card-glow">
            <h2 class="chart-title">
              <i class="ri-pie-chart-line"></i> 위험도 분포
            </h2>
            <div class="danger-chart">
              <div v-for="lvl in dangerOrder" :key="lvl" class="danger-row">
                <div class="danger-info">
                  <div class="danger-dot" :class="'danger-dot-' + lvl"></div>
                  <span class="danger-label">{{ dangerLabel[lvl] }}</span>
                </div>
                <div class="danger-bar-wrap">
                  <div
                    class="danger-bar"
                    :class="'danger-bar-' + lvl"
                    :style="{ width: barPct(data.danger_breakdown[lvl]) + '%' }"
                  ></div>
                </div>
                <span class="danger-count">{{ data.danger_breakdown[lvl] || 0 }}</span>
                <span class="danger-pct">{{ barPct(data.danger_breakdown[lvl]) }}%</span>
              </div>
            </div>
          </div>

          <!-- Top Cameras -->
          <div class="card card-glow">
            <h2 class="chart-title">
              <i class="ri-camera-line"></i> 카메라 당 건수
            </h2>
            <div v-if="data.top_cameras.length === 0" class="empty-mini">
              <i class="ri-inbox-line"></i>
              <span>데이터 없음</span>
            </div>
            <div v-else class="camera-list">
              <div v-for="(c, i) in data.top_cameras" :key="i" class="camera-row">
                <div class="camera-rank" :class="{ 'camera-rank-top': i < 3 }">{{ i + 1 }}</div>
                <div class="camera-name-wrap">
                  <span class="camera-name">{{ c.camera }}</span>
                  <div class="camera-bar-bg">
                    <div
                      class="camera-bar"
                      :style="{ width: (c.count / camMax) * 100 + '%' }"
                    ></div>
                  </div>
                </div>
                <span class="camera-count">{{ c.count }}</span>
              </div>
            </div>
          </div>
        </div>

        <!-- Charts Row 2 -->
        <div class="chart-row">
          <!-- Daily Trend -->
          <div class="card card-glow">
            <h2 class="chart-title">
              <i class="ri-line-chart-line"></i> 일자별 추이
            </h2>
            <div class="daily-chart">
              <div class="daily-bars">
                <div
                  v-for="(d, i) in data.by_day"
                  :key="i"
                  class="daily-bar-col"
                  :title="d.date + ': ' + d.count"
                >
                  <div class="daily-bar-wrap">
                    <div
                      class="daily-bar"
                      :style="{ height: barH(d.count, dayMax, 84) + 'px' }"
                    ></div>
                  </div>
                </div>
              </div>
              <div class="daily-labels">
                <div v-for="(d, i) in data.by_day" :key="i" class="daily-label-col">
                  <span class="daily-date">{{ d.date.slice(5) }}</span>
                  <span class="daily-count">{{ d.count }}</span>
                </div>
              </div>
            </div>
          </div>

          <!-- Hourly Distribution -->
          <div class="card card-glow">
            <h2 class="chart-title">
              <i class="ri-time-line"></i> 시간대별 (0&ndash;23시)
            </h2>
            <div class="hourly-chart">
              <div class="hourly-bars">
                <div
                  v-for="h in data.by_hour"
                  :key="h.hour"
                  class="hourly-bar-col"
                  :title="h.hour + 'h: ' + h.count"
                >
                  <div class="hourly-bar-wrap">
                    <div
                      class="hourly-bar"
                      :class="{ 'hourly-bar-hot': h.count >= hourHotThreshold }"
                      :style="{ height: barH(h.count, hourMax, 60) + 'px' }"
                    ></div>
                  </div>
                </div>
              </div>
              <div class="hourly-labels">
                <div
                  v-for="h in data.by_hour"
                  :key="h.hour"
                  class="hourly-label-col"
                >
                  <span class="hourly-hour">{{ h.hour }}</span>
                </div>
              </div>
            </div>
            <div class="hourly-legend">
              <div class="legend-item">
                <div class="legend-dot legend-dot-accent"></div>
                <span class="legend-text">일반 시간대</span>
              </div>
              <div class="legend-item">
                <div class="legend-dot legend-dot-hot"></div>
                <span class="legend-text">피크 시간대 ({{ hourHotThreshold }}+건)</span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </main>
  </div>
</template>

<script>
export default { name: 'ReportView' }
</script>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useTheme } from '../composables/useTheme.js'
import { getReportSummary } from '../api/reports.js'

/* ── Theme ── */
const { isDark, toggle: toggleTheme } = useTheme()

/* ── State ── */
const days = ref(7)
const data = ref(null)
const loading = ref(false)
const error = ref('')

const dangerOrder = ['critical', 'high', 'low']
const dangerLabel = { critical: '심각', high: '높음', low: '낮음' }

/* ── Computed ── */
const dangerMax = computed(() => {
  if (!data.value) return 1
  return Math.max(1, ...dangerOrder.map(l => data.value.danger_breakdown[l] || 0))
})
const dayMax = computed(() => {
  if (!data.value) return 1
  return Math.max(1, ...(data.value.by_day || []).map(d => d.count))
})
const hourMax = computed(() => {
  if (!data.value) return 1
  return Math.max(1, ...(data.value.by_hour || []).map(h => h.count))
})
const hourHotThreshold = computed(() => {
  return Math.max(3, Math.ceil(hourMax.value * 0.55))
})
const camMax = computed(() => {
  if (!data.value?.top_cameras?.length) return 1
  return Math.max(1, ...data.value.top_cameras.map(c => c.count))
})
const criticalPct = computed(() => {
  if (!data.value) return 0
  return Math.round(((data.value.danger_breakdown.critical || 0) / data.value.total) * 100)
})
const avgPerDay = computed(() => {
  if (!data.value) return '-'
  return (data.value.total / data.value.days).toFixed(1)
})
const peakDay = computed(() => {
  if (!data.value?.by_day?.length) return '-'
  return Math.max(...data.value.by_day.map(d => d.count))
})

function barPct(n) {
  return Math.round(((n || 0) / dangerMax.value) * 100)
}
function barH(n, max, maxPx) {
  if (!n || !max) return 2
  return Math.round(((n || 0) / max) * maxPx)
}

/* ── Methods ── */
async function onPeriodChange(d) {
  if (days.value === d) return
  days.value = d
  await load()
}

async function load() {
  loading.value = true
  error.value = ''
  try {
    data.value = await getReportSummary(days.value)
  } catch (e) {
    error.value = e.response?.data?.detail ?? e.message ?? '데이터 불러오기 중 오류가 발생했습니다.'
    data.value = null
  } finally {
    loading.value = false
  }
}

onMounted(load)
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
  --c-amber: #f59e0b;
  --c-amber-soft: #fffbeb;
  --c-blue-soft: #eff6ff;
  --c-blue-text: #3b82f6;
  --c-green: #22c55e;
  --c-green-soft: #f0fdf4;
  --c-orange: #f97316;
  --c-orange-soft: #fff7ed;
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
  --c-amber-soft: #2d2010;
  --c-blue-soft: #1a2540;
  --c-green-soft: #122a1a;
  --c-orange-soft: #2d1a10;
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

/* Period Pill Selector */
.period-pills { display: flex; align-items: center; gap: 6px; margin-left: auto; }
.period-pill {
  font-size: 12px; padding: 5px 16px; border-radius: 999px;
  border: 1px solid var(--c-border); background: var(--c-bg-card);
  color: var(--c-text-secondary); font-weight: 500;
  transition: all 0.15s; cursor: pointer;
}
.period-pill:hover { border-color: var(--c-text-muted); color: var(--c-text); }
.period-pill-active {
  background: var(--c-accent); color: #fff; border-color: var(--c-accent); font-weight: 600;
}
.period-pill-active:hover { background: var(--c-accent-hover); border-color: var(--c-accent-hover); color: #fff; }

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

/* ═══════════════════════════ Overview Cards ═══════════════════════════ */
.overview-row {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 14px; margin-bottom: 16px;
}
.overview-card {
  padding: 18px 20px;
}
.overview-card-danger {
  border-left: 3px solid var(--c-red);
}
.overview-label {
  display: flex; align-items: center; gap: 6px;
  font-size: 11px; color: var(--c-text-muted); font-weight: 500;
  margin-bottom: 8px;
}
.overview-label i { font-size: 13px; color: var(--c-text-muted); }

.overview-value {
  display: flex; align-items: baseline; gap: 4px; margin-bottom: 6px;
}
.overview-number {
  font-size: 28px; font-weight: 700; color: var(--c-text);
  font-family: 'JetBrains Mono', monospace; letter-spacing: -0.02em;
}
.overview-unit {
  font-size: 13px; color: var(--c-text-muted); font-weight: 500;
}
.overview-sub {
  display: flex; align-items: center; gap: 4px;
  font-size: 11px;
}
.trend-up { color: var(--c-red); display: flex; align-items: center; gap: 3px; font-weight: 500; }
.trend-down { color: var(--c-green); display: flex; align-items: center; gap: 3px; font-weight: 500; }
.trend-flat { color: var(--c-text-muted); display: flex; align-items: center; gap: 3px; }
.overview-sub-text { color: var(--c-text-muted); }

/* ═══════════════════════════ Chart Rows ═══════════════════════════ */
.chart-row {
  display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin-bottom: 14px;
}
.chart-title {
  font-size: 13px; font-weight: 600; color: var(--c-text);
  display: flex; align-items: center; gap: 6px; margin-bottom: 16px;
}
.chart-title i { font-size: 14px; color: var(--c-accent-hover); }

/* ═══════════════════════════ Danger Chart ═══════════════════════════ */
.danger-chart {
  display: flex; flex-direction: column; gap: 12px;
}
.danger-row {
  display: flex; align-items: center; gap: 10px;
}
.danger-info {
  display: flex; align-items: center; gap: 6px; min-width: 56px; flex-shrink: 0;
}
.danger-dot {
  width: 10px; height: 10px; border-radius: 3px; flex-shrink: 0;
}
.danger-dot-critical { background: #b91c1c; }
.danger-dot-high { background: var(--c-orange); }
.danger-dot-low { background: var(--c-amber); }
.danger-dot-info { background: var(--c-blue-text); }

.danger-label { font-size: 12px; color: var(--c-text-secondary); font-weight: 500; }

.danger-bar-wrap {
  flex: 1; height: 10px; border-radius: 999px;
  background: var(--c-bg-elevated); overflow: hidden;
}
.danger-bar {
  height: 100%; border-radius: 999px; transition: width 0.5s ease;
}
.danger-bar-critical { background: #b91c1c; }
.danger-bar-high { background: var(--c-orange); }
.danger-bar-low { background: var(--c-amber); }
.danger-bar-info { background: var(--c-blue-text); }

.danger-count {
  font-size: 12px; color: var(--c-text); font-weight: 500;
  font-family: 'JetBrains Mono', monospace; min-width: 30px; text-align: right;
}
.danger-pct {
  font-size: 11px; color: var(--c-text-muted);
  font-family: 'JetBrains Mono', monospace; min-width: 32px; text-align: right;
}

/* ═══════════════════════════ Camera List ═══════════════════════════ */
.camera-list {
  display: flex; flex-direction: column; gap: 8px;
}
.camera-row {
  display: flex; align-items: center; gap: 10px;
}
.camera-rank {
  width: 24px; height: 24px; border-radius: 6px;
  background: var(--c-bg-elevated); display: flex; align-items: center; justify-content: center;
  font-size: 11px; font-weight: 600; color: var(--c-text-muted);
  font-family: 'JetBrains Mono', monospace; flex-shrink: 0;
}
.camera-rank-top {
  background: var(--c-accent-soft); color: var(--c-accent-hover);
}
.camera-name-wrap {
  flex: 1; min-width: 0; display: flex; flex-direction: column; gap: 4px;
}
.camera-name { font-size: 12px; color: var(--c-text); font-weight: 500; }
.camera-bar-bg {
  height: 4px; border-radius: 999px;
  background: var(--c-bg-elevated); overflow: hidden;
}
.camera-bar {
  height: 100%; border-radius: 999px;
  background: var(--c-accent); transition: width 0.5s ease;
}
.camera-count {
  font-size: 12px; color: var(--c-text-secondary); font-weight: 500;
  font-family: 'JetBrains Mono', monospace; flex-shrink: 0;
}

.empty-mini {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 24px 0; gap: 6px;
}
.empty-mini i { font-size: 16px; color: var(--c-text-muted); }
.empty-mini span { font-size: 12px; color: var(--c-text-muted); }

/* ═══════════════════════════ Daily Chart ═══════════════════════════ */
.daily-chart {
  display: flex; flex-direction: column; gap: 4px;
}
.daily-bars {
  display: flex; align-items: flex-end; gap: 2px; height: 88px;
}
.daily-bar-col {
  flex: 1; display: flex; flex-direction: column; justify-content: flex-end; height: 100%;
  cursor: pointer;
}
.daily-bar-wrap {
  width: 100%; display: flex; flex-direction: column; justify-content: flex-end;
}
.daily-bar {
  width: 100%; min-height: 2px; border-radius: 3px 3px 0 0;
  background: var(--c-accent); transition: height 0.4s ease;
}
.daily-bar-col:hover .daily-bar { opacity: 0.75; }

.daily-labels {
  display: flex; gap: 2px;
}
.daily-label-col {
  flex: 1; display: flex; flex-direction: column; align-items: center; gap: 1px;
}
.daily-date {
  font-size: 9px; color: var(--c-text-muted);
  font-family: 'JetBrains Mono', monospace; line-height: 1;
}
.daily-count {
  font-size: 9px; color: var(--c-text-muted);
  font-family: 'JetBrains Mono', monospace; line-height: 1;
}

/* ═══════════════════════════ Hourly Chart ═══════════════════════════ */
.hourly-chart {
  display: flex; flex-direction: column; gap: 2px;
}
.hourly-bars {
  display: flex; align-items: flex-end; gap: 1px; height: 64px;
}
.hourly-bar-col {
  flex: 1; display: flex; flex-direction: column; justify-content: flex-end; height: 100%;
  cursor: pointer;
}
.hourly-bar-wrap {
  width: 100%; display: flex; flex-direction: column; justify-content: flex-end;
}
.hourly-bar {
  width: 100%; min-height: 1px; border-radius: 1px 1px 0 0;
  background: var(--c-accent-soft); border-top: 2px solid var(--c-accent-border);
  transition: height 0.4s ease;
}
.hourly-bar-hot {
  background: var(--c-orange-soft); border-top-color: var(--c-orange);
}
.hourly-bar-col:hover .hourly-bar { opacity: 0.7; }

.hourly-labels {
  display: flex; gap: 1px;
}
.hourly-label-col {
  flex: 1; display: flex; flex-direction: column; align-items: center;
}
.hourly-hour {
  font-size: 8px; color: var(--c-text-muted);
  font-family: 'JetBrains Mono', monospace; line-height: 1;
}

.hourly-legend {
  display: flex; align-items: center; gap: 14px; margin-top: 10px;
}
.legend-item {
  display: flex; align-items: center; gap: 5px;
}
.legend-dot {
  width: 8px; height: 8px; border-radius: 2px; flex-shrink: 0;
}
.legend-dot-accent { background: var(--c-accent-border); }
.legend-dot-hot { background: var(--c-orange); }
.legend-text { font-size: 10px; color: var(--c-text-muted); }

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
@keyframes spin { to { transform: rotate(360deg); } }

.loading-center {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 64px 0; gap: 12px;
}
.loading-center p { font-size: 12px; color: var(--c-text-muted); }

/* ═══════════════════════════ Error ═══════════════════════════ */
.error-box {
  display: flex; align-items: flex-start; gap: 12px; padding: 16px;
  border-radius: 12px; background: var(--c-red-soft); border: 1px solid rgba(239,68,68,0.2);
}
.error-box i { color: var(--c-red); font-size: 18px; margin-top: 1px; flex-shrink: 0; }
.error-title { font-size: 13px; font-weight: 600; color: var(--c-red); margin-bottom: 4px; }
.error-detail { font-size: 12px; color: var(--c-red); opacity: 0.8; margin-bottom: 8px; }
.error-box .btn-ghost { margin-top: 2px; }

/* ═══════════════════════════ Responsive ═══════════════════════════ */
@media (max-width: 1024px) {
  .topnav-links { display: none; }
  .nav-divider { display: none; }
  .overview-row { grid-template-columns: 1fr; }
  .chart-row { grid-template-columns: 1fr; }
  .page-desc { display: none; }
  .daily-date { font-size: 7px; }
  .daily-count { font-size: 7px; }
  .hourly-hour { font-size: 7px; }
  .hourly-legend { flex-direction: column; align-items: flex-start; gap: 4px; }
}
</style>
