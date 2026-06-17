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
          <i class="ri-building-line"></i>
        </div>
        <div>
          <h1 class="page-title">Zone Inspection</h1>
          <p class="page-desc">구역별 안전 점검 항목과 체크리스트를 확인할 수 있습니다.</p>
        </div>
        <!-- Stats summary -->
        <div v-if="zones.length && !loading" class="stats-row">
          <div class="stat-chip">
            <i class="ri-map-pin-line"></i>
            <span>{{ zones.length }} 구역</span>
          </div>
          <div class="stat-chip">
            <i class="ri-check-double-line"></i>
            <span>{{ totalItems }} 항목</span>
          </div>
        </div>
      </div>

      <!-- Loading -->
      <div v-if="loading" class="loading-center">
        <span class="spinner spinner-accent"></span>
        <p>구역 데이터 불러오는 중...</p>
      </div>

      <!-- Empty -->
      <div v-else-if="zones.length === 0" class="empty-center">
        <div class="empty-icon-box">
          <i class="ri-building-line"></i>
        </div>
        <p class="empty-title">등록된 구역이 없습니다</p>
        <p class="empty-desc">매뉴얼 탭에서 구역을 등록하고 PDF 분석을 완료하면 여기서 점검 항목을 확인할 수 있습니다.</p>
        <button class="btn-ghost" @click="$router && $router.push && $router.push('/manual')">
          <i class="ri-arrow-right-line"></i> 매뉴얼로 이동
        </button>
      </div>

      <!-- Zone Grid -->
      <div v-else class="zone-grid">
        <div v-for="z in zones" :key="z.zone" class="card card-glow zone-card">
          <!-- Card Header -->
          <div class="zone-card-header">
            <div class="zone-icon-box">
              <i class="ri-map-pin-line"></i>
            </div>
            <div class="zone-header-info">
              <h2 class="zone-name">{{ z.zone }}</h2>
              <span class="zone-badge">
                {{ z.static.length + z.dynamic.length }} 항목
              </span>
            </div>
          </div>

          <!-- Divider -->
          <div class="zone-divider"></div>

          <!-- Static Items -->
          <div v-if="z.static.length" class="zone-section">
            <div class="zone-section-label">
              <div class="section-dot section-dot-static"></div>
              <span>정적</span>
              <span class="section-count">{{ z.static.length }}</span>
            </div>
            <ul class="zone-items">
              <li v-for="(it, i) in z.static" :key="'s'+i" class="zone-item">
                <span class="zone-item-bullet"></span>
                <span class="zone-item-text">{{ it }}</span>
              </li>
            </ul>
          </div>

          <!-- Dynamic Items -->
          <div v-if="z.dynamic.length" class="zone-section" :class="{ 'zone-section-gap': z.static.length }">
            <div class="zone-section-label">
              <div class="section-dot section-dot-dynamic"></div>
              <span>동적</span>
              <span class="section-count">{{ z.dynamic.length }}</span>
            </div>
            <ul class="zone-items">
              <li v-for="(it, i) in z.dynamic" :key="'d'+i" class="zone-item">
                <span class="zone-item-bullet zone-item-bullet-dynamic"></span>
                <span class="zone-item-text">{{ it }}</span>
              </li>
            </ul>
          </div>

          <!-- Empty State within card -->
          <div v-if="!z.static.length && !z.dynamic.length" class="zone-empty">
            <i class="ri-inbox-line"></i>
            <span>점검 항목 미설정</span>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script>
export default { name: 'ZoneView' }
</script>

<script setup>
import { computed, onMounted, onActivated } from 'vue'
import { storeToRefs } from 'pinia'
import { useTheme } from '../composables/useTheme.js'
import { useManualStore } from '../stores/manualStore.js'
import { fetchZones, fetchChecklist } from '../api/manuals.js'

const { isDark, toggle: toggleTheme } = useTheme()

const store = useManualStore()
const { zoneViewData, zoneViewLoaded } = storeToRefs(store)

const zones = computed(() => zoneViewData.value)
const loading = computed(() => !zoneViewLoaded.value && zoneViewData.value.length === 0)
const totalItems = computed(() => {
  let total = 0
  for (const z of zoneViewData.value) total += z.static.length + z.dynamic.length
  return total
})

async function loadZones() {
  if (zoneViewLoaded.value) return
  try {
    const [names, cl] = await Promise.all([fetchZones(), fetchChecklist()])
    const byName = {}
    for (const z of (cl.zones || [])) byName[z.zone] = z
    zoneViewData.value = (names || []).map(name => ({
      zone: name,
      static: byName[name]?.static || [],
      dynamic: byName[name]?.dynamic || [],
    }))
  } catch {
    zoneViewData.value = []
  } finally {
    zoneViewLoaded.value = true
  }
}

onMounted(loadZones)
onActivated(loadZones)
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
  --c-amber: #f59e0b;
  --c-amber-soft: #fffbeb;
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
  --c-amber-soft: #2d2010;
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

/* Stats summary row */
.stats-row { display: flex; align-items: center; gap: 8px; margin-left: auto; }
.stat-chip {
  display: flex; align-items: center; gap: 5px;
  font-size: 11px; padding: 5px 12px; border-radius: 999px;
  background: var(--c-bg-elevated); color: var(--c-text-secondary);
  border: 1px solid var(--c-border); font-weight: 500;
}
.stat-chip i { font-size: 12px; color: var(--c-accent-hover); }

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

/* ═══════════════════════════ Zone Grid ═══════════════════════════ */
.zone-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}

.zone-card {
  padding: 0;
  display: flex;
  flex-direction: column;
}

/* Card Header */
.zone-card-header {
  display: flex; align-items: center; gap: 10px;
  padding: 18px 20px 14px;
}
.zone-icon-box {
  width: 36px; height: 36px; border-radius: 10px;
  background: var(--c-accent-soft); display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.zone-icon-box i { color: var(--c-accent-hover); font-size: 16px; }
.zone-header-info { display: flex; flex-direction: column; gap: 2px; }
.zone-name { font-size: 14px; font-weight: 600; color: var(--c-text); }
.zone-badge {
  font-size: 10px; padding: 2px 8px; border-radius: 999px;
  background: var(--c-accent-soft); color: var(--c-accent-hover);
  border: 1px solid var(--c-accent-border); font-weight: 600;
  display: inline-flex; align-self: flex-start;
}

.zone-divider {
  height: 1px; background: var(--c-border-light);
  margin: 0 20px;
}

/* Zone Sections */
.zone-section {
  padding: 14px 20px;
}
.zone-section-gap {
  border-top: 1px solid var(--c-border-light);
}

.zone-section-label {
  display: flex; align-items: center; gap: 6px;
  margin-bottom: 10px;
}
.section-dot {
  width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0;
}
.section-dot-static { background: var(--c-accent); }
.section-dot-dynamic { background: var(--c-amber); }

.zone-section-label span:first-of-type {
  font-size: 11px; font-weight: 600; color: var(--c-text-secondary);
  text-transform: uppercase; letter-spacing: 0.05em;
}
.section-count {
  font-size: 10px; color: var(--c-text-muted);
  font-family: 'JetBrains Mono', monospace;
}

/* Zone Items */
.zone-items { list-style: none; display: flex; flex-direction: column; gap: 6px; }
.zone-item {
  display: flex; align-items: flex-start; gap: 8px;
  padding: 7px 10px; border-radius: 8px;
  background: var(--c-bg-elevated); border: 1px solid var(--c-border);
  transition: all 0.15s;
}
.zone-item:hover { border-color: var(--c-text-muted); }
.zone-item-bullet {
  width: 4px; height: 4px; border-radius: 50%;
  background: var(--c-accent); flex-shrink: 0; margin-top: 6px;
}
.zone-item-bullet-dynamic { background: var(--c-amber); }
.zone-item-text {
  font-size: 12px; color: var(--c-text); line-height: 1.5;
}

/* Empty state within card */
.zone-empty {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 24px 20px; gap: 6px;
}
.zone-empty i { font-size: 18px; color: var(--c-text-muted); }
.zone-empty span { font-size: 12px; color: var(--c-text-muted); }

/* ═══════════════════════════ Buttons ═══════════════════════════ */
.btn-ghost {
  font-size: 12px; padding: 6px 14px; border-radius: 8px; border: 1px solid var(--c-border);
  background: var(--c-bg-elevated); color: var(--c-text-secondary);
  display: flex; align-items: center; gap: 5px; transition: all 0.2s;
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

/* ═══════════════════════════ Empty ═══════════════════════════ */
.empty-center {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 64px 0;
}
.empty-icon-box {
  width: 48px; height: 48px; border-radius: 12px;
  background: var(--c-bg-elevated); border: 1px solid var(--c-border);
  display: flex; align-items: center; justify-content: center;
  margin-bottom: 12px;
}
.empty-icon-box i { font-size: 20px; color: var(--c-text-muted); }
.empty-title { font-size: 14px; font-weight: 600; color: var(--c-text); margin-bottom: 4px; }
.empty-desc { font-size: 12px; color: var(--c-text-muted); margin-bottom: 16px; text-align: center; }

/* ═══════════════════════════ Responsive ═══════════════════════════ */
@media (max-width: 1024px) {
  .topnav-links { display: none; }
  .nav-divider { display: none; }
  .zone-grid { grid-template-columns: 1fr; }
  .page-desc { display: none; }
  .stats-row { display: none; }
}

@media (min-width: 1400px) {
  .zone-grid { grid-template-columns: repeat(3, 1fr); }
}
</style>
