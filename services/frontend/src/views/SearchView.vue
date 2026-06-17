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
          <i class="ri-search-eye-line"></i>
        </div>
        <div>
          <h1 class="page-title">Event Search</h1>
          <p class="page-desc">자연어 검색, 날짜, 채널 필터를 활용해 CCTV 이벤트를 빠르게 찾을 수 있습니다.</p>
        </div>
      </div>

      <!-- Search Bar Card -->
      <div class="card card-glow search-card">
        <div class="search-bar-wrap">
          <div class="search-icon-left">
            <i class="ri-search-line"></i>
          </div>
          <input
            v-model="searchQuery"
            type="text"
            class="search-input"
            placeholder="예: 오늘 오후 1번 카메라에서 움직임 감지"
            @keydown.enter="handleSearch(searchQuery)"
          />
          <button class="btn-search" @click="handleSearch(searchQuery)">
            <i class="ri-search-line"></i>
            <span>검색</span>
          </button>
        </div>

        <!-- Filter info row -->
        <div class="filter-info-row">
          <!-- Natural language filter chip -->
          <div v-if="appliedFilter && !selectedQuickFilter" class="nl-filter-chip">
            <span class="nl-filter-label">검색어에서 감지:</span>
            <span class="nl-filter-tag">
              {{ appliedFilter }}
              <button class="nl-filter-remove" @click="clearAppliedFilter">×</button>
            </span>
          </div>
          <!-- Active filters summary -->
          <div v-if="activeFilterSummary" class="active-summary">
            {{ activeFilterSummary }}
          </div>
        </div>
      </div>

      <!-- Quick Date Filters -->
      <div class="filter-section">
        <span class="filter-section-label">기간</span>
        <div class="filter-pills">
          <button
            v-for="f in QUICK_FILTERS"
            :key="f.key"
            class="filter-pill"
            :class="{ 'filter-pill-active': selectedQuickFilter === f.key }"
            @click="handleQuickFilter(f.key)"
          >{{ f.label }}</button>
        </div>
      </div>

      <!-- Channel Filter -->
      <div class="filter-section">
        <span class="filter-section-label">채널</span>
        <div class="filter-pills">
          <button
            class="filter-pill"
            :class="{ 'filter-pill-active': selectedChannelId === null }"
            @click="handleChannelChange(null)"
          >전체</button>
          <button
            v-for="ch in channels"
            :key="ch.camera_id"
            class="filter-pill"
            :class="{ 'filter-pill-active': selectedChannelId === ch.camera_id }"
            @click="handleChannelChange(ch.camera_id)"
          >{{ ch.name }}</button>
        </div>
      </div>

      <!-- Results -->
      <div class="results-area">
        <ResultList :events="events" :loading="loading" :error="error" />
      </div>
    </main>
  </div>
</template>

<script>
export default { name: 'SearchView' }
</script>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { useTheme } from '../composables/useTheme.js'
import ResultList    from '../components/search/ResultList.vue'
import { useEvents }    from '../composables/useEvents.js'
import { useChannels }  from '../composables/useChannels.js'
import { useEventStore } from '../stores/eventStore.js'

const { isDark, toggle: toggleTheme } = useTheme()

const { events, loading, error, appliedFilter, load, search } = useEvents()
const { slots } = useChannels()
const channels = computed(() => slots.value.filter(Boolean))
const eventStore = useEventStore()

const selectedChannelId   = ref(null)
const lastQuery           = ref('')
const selectedQuickFilter = ref(null)
const searchQuery         = ref('')

onMounted(load)

const QUICK_FILTERS = [
  { key: 'today',      label: '오늘' },
  { key: 'this_week',  label: '이번 주' },
  { key: 'last_7',     label: '지난 7일' },
  { key: 'this_month', label: '이번 달' },
]

const activeFilterSummary = computed(() => {
  const parts = []
  if (selectedQuickFilter.value) {
    const f = QUICK_FILTERS.find(q => q.key === selectedQuickFilter.value)
    if (f) parts.push(f.label)
  }
  if (selectedChannelId.value) {
    const ch = channels.value.find(c => c.camera_id === selectedChannelId.value)
    if (ch) parts.push(ch.name)
  }
  return parts.length ? '활성 필터: ' + parts.join(' · ') : ''
})

function getQuickFilterDates(key) {
  const now      = new Date()
  const dayStart = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).toISOString()

  if (key === 'today')      return { startDate: dayStart(now), endDate: now.toISOString() }
  if (key === 'this_week') {
    const monday = new Date(now)
    const day = now.getDay()
    monday.setDate(now.getDate() - (day === 0 ? 6 : day - 1))
    return { startDate: dayStart(monday), endDate: now.toISOString() }
  }
  if (key === 'last_7') {
    const start = new Date(now)
    start.setDate(start.getDate() - 7)
    return { startDate: dayStart(start), endDate: now.toISOString() }
  }
  if (key === 'this_month') {
    return {
      startDate: new Date(now.getFullYear(), now.getMonth(), 1).toISOString(),
      endDate:   now.toISOString(),
    }
  }
  return { startDate: null, endDate: null }
}

async function handleSearch(query, startDate = null, endDate = null, skipTimeParse = false) {
  lastQuery.value = query
  if (!query.trim()) {
    await load(selectedChannelId.value ? { channel_id: selectedChannelId.value } : {})
  } else {
    await search(query, selectedChannelId.value, startDate, endDate, skipTimeParse)
  }
  eventStore.setSearchResults(events.value)
}

async function handleQuickFilter(key) {
  if (selectedQuickFilter.value === key) {
    selectedQuickFilter.value = null
    if (lastQuery.value) {
      await handleSearch(lastQuery.value)
    } else {
      await load(selectedChannelId.value ? { channel_id: selectedChannelId.value } : {})
    }
    return
  }
  selectedQuickFilter.value = key
  const { startDate, endDate } = getQuickFilterDates(key)
  if (lastQuery.value) {
    await handleSearch(lastQuery.value, startDate, endDate)
  }
}

async function clearAppliedFilter() {
  await handleSearch(lastQuery.value, null, null, true)
}

async function handleChannelChange(channelId) {
  selectedChannelId.value = channelId
  if (lastQuery.value) {
    const dates = selectedQuickFilter.value
      ? getQuickFilterDates(selectedQuickFilter.value)
      : { startDate: null, endDate: null }
    await handleSearch(lastQuery.value, dates.startDate, dates.endDate)
  } else {
    await load(channelId ? { channel_id: channelId } : {})
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
  min-height: 64px; display: flex; align-items: center;
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

.topnav-actions { display: flex; align-items: center; gap: 14px; }
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

.search-card { margin-bottom: 16px; }

/* ═══════════════════════════ Search Bar ═══════════════════════════ */
.search-bar-wrap {
  display: flex; align-items: center; gap: 0;
  background: var(--c-bg-elevated); border: 1px solid var(--c-border);
  border-radius: 12px; overflow: hidden; transition: border 0.2s;
}
.search-bar-wrap:focus-within { border-color: var(--c-accent-border); }

.search-icon-left {
  padding: 0 12px; display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.search-icon-left i { font-size: 16px; color: var(--c-text-muted); }

.search-input {
  flex: 1; padding: 12px 0; border: none; outline: none;
  background: transparent; font-size: 14px; color: var(--c-text);
}
.search-input::placeholder { color: var(--c-text-muted); font-size: 13px; }

.btn-search {
  display: flex; align-items: center; gap: 6px;
  padding: 10px 20px; margin: 4px; border-radius: 10px; border: none;
  background: var(--c-accent); color: #fff; font-size: 13px; font-weight: 600;
  transition: all 0.2s; flex-shrink: 0;
}
.btn-search:hover { background: var(--c-accent-hover); }
.btn-search i { font-size: 14px; }

.filter-info-row { margin-top: 12px; min-height: 0; }

/* Natural Language Filter Chip */
.nl-filter-chip { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; }
.nl-filter-label { font-size: 11px; color: var(--c-text-muted); flex-shrink: 0; }
.nl-filter-tag {
  display: inline-flex; align-items: center; gap: 4px;
  font-size: 11px; padding: 4px 10px; border-radius: 999px;
  background: var(--c-accent-soft); color: var(--c-accent-hover);
  border: 1px solid var(--c-accent-border); font-weight: 500;
}
.nl-filter-remove {
  background: none; border: none; color: var(--c-text-muted);
  font-size: 13px; padding: 0 2px; line-height: 1; cursor: pointer;
}
.nl-filter-remove:hover { color: var(--c-text-secondary); }

.active-summary { font-size: 11px; color: var(--c-text-muted); }

/* ═══════════════════════════ Filter Sections ═══════════════════════════ */
.filter-section { margin-bottom: 12px; display: flex; align-items: flex-start; gap: 12px; }
.filter-section-label {
  font-size: 11px; font-weight: 600; text-transform: uppercase;
  letter-spacing: 0.05em; color: var(--c-text-muted);
  padding-top: 6px; flex-shrink: 0; min-width: 36px;
}

.filter-pills { display: flex; flex-wrap: wrap; gap: 6px; }
.filter-pill {
  font-size: 12px; padding: 5px 14px; border-radius: 999px;
  border: 1px solid var(--c-border); background: var(--c-bg-card);
  color: var(--c-text-secondary); font-weight: 500;
  transition: all 0.15s; cursor: pointer;
}
.filter-pill:hover { border-color: var(--c-text-muted); color: var(--c-text); }
.filter-pill-active {
  background: var(--c-accent); color: #fff; border-color: var(--c-accent); font-weight: 600;
}
.filter-pill-active:hover { background: var(--c-accent-hover); border-color: var(--c-accent-hover); color: #fff; }

/* ═══════════════════════════ Results Area ═══════════════════════════ */
.results-area { min-height: 200px; }

.results-header { margin-bottom: 12px; }
.results-count { font-size: 12px; color: var(--c-text-muted); }
.results-count strong { color: var(--c-text); font-weight: 600; }

/* Event Cards */
.event-list { display: flex; flex-direction: column; gap: 10px; }

.event-card {
  display: flex; align-items: flex-start; gap: 14px;
  padding: 14px; border-radius: 12px;
  background: var(--c-bg-card); border: 1px solid var(--c-border-light);
  transition: all 0.2s;
}
.event-card:hover { border-color: var(--c-accent-border); }

.event-thumb {
  position: relative; width: 160px; height: 90px; flex-shrink: 0;
  border-radius: 8px; overflow: hidden;
}
.event-thumb img {
  width: 100%; height: 100%; object-fit: cover; display: block;
}
.event-badge {
  position: absolute; top: 6px; left: 6px;
  font-size: 10px; padding: 2px 8px; border-radius: 999px;
  font-weight: 600; color: #fff; letter-spacing: 0.03em;
}
.badge-critical { background: var(--c-red); }
.badge-warning { background: var(--c-amber); }
.badge-info { background: var(--c-blue-text); }

.event-info { flex: 1; min-width: 0; }
.event-top-row { display: flex; align-items: center; gap: 8px; margin-bottom: 4px; }
.event-title { font-size: 14px; font-weight: 600; color: var(--c-text); }
.event-time {
  font-size: 11px; color: var(--c-text-muted); flex-shrink: 0;
  font-family: 'JetBrains Mono', monospace; margin-left: auto;
}
.event-desc {
  font-size: 12px; color: var(--c-text-secondary); line-height: 1.5;
  display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical;
  overflow: hidden; margin-bottom: 8px;
}
.event-meta { display: flex; flex-wrap: wrap; gap: 12px; }
.event-meta-item {
  font-size: 11px; color: var(--c-text-muted); display: flex; align-items: center; gap: 4px;
}
.event-meta-item i { font-size: 12px; }

.event-action { display: flex; align-items: center; padding-top: 4px; flex-shrink: 0; }

/* ═══════════════════════════ Buttons ═══════════════════════════ */
.btn-ghost {
  font-size: 12px; padding: 6px 14px; border-radius: 8px; border: 1px solid var(--c-border);
  background: var(--c-bg-elevated); color: var(--c-text-secondary);
  display: flex; align-items: center; gap: 5px; transition: all 0.2s;
}
.btn-ghost:hover { background: var(--c-border); }

.btn-search-small {
  font-size: 11px; padding: 5px 12px; border-radius: 6px; border: none;
  background: var(--c-accent); color: #fff; font-weight: 600;
  display: flex; align-items: center; gap: 4px; transition: all 0.2s;
}
.btn-search-small:hover { background: var(--c-accent-hover); }

.btn-remove { background: none; border: none; color: var(--c-text-muted); font-size: 16px; flex-shrink: 0; padding: 2px; transition: color 0.15s; }
.btn-remove:hover { color: var(--c-text-secondary); }

/* ═══════════════════════════ Error ═══════════════════════════ */
.error-box {
  display: flex; align-items: flex-start; gap: 12px; padding: 16px;
  border-radius: 12px; background: var(--c-red-soft); border: 1px solid rgba(239,68,68,0.2);
}
.error-box i { color: var(--c-red); font-size: 18px; margin-top: 1px; flex-shrink: 0; }
.error-title { font-size: 13px; font-weight: 600; color: var(--c-red); margin-bottom: 4px; }
.error-detail { font-size: 12px; color: var(--c-red); opacity: 0.8; margin-bottom: 8px; }
.error-box .btn-ghost { margin-top: 2px; }

/* ═══════════════════════════ Spinner ═══════════════════════════ */
.spinner-accent {
  display: inline-block; width: 32px; height: 32px;
  border: 3px solid var(--c-accent-soft); border-top-color: var(--c-accent);
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.loading-center {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 48px 0; gap: 12px;
}
.loading-center p { font-size: 12px; color: var(--c-text-muted); }

/* ═══════════════════════════ Empty ═══════════════════════════ */
.empty-center {
  display: flex; flex-direction: column; align-items: center; justify-content: center;
  padding: 48px 0;
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

.search-examples {
  display: flex; flex-direction: column; align-items: center; gap: 8px;
}
.example-label { font-size: 11px; color: var(--c-text-muted); font-weight: 500; }
.example-chip {
  font-size: 12px; padding: 6px 14px; border-radius: 999px;
  border: 1px solid var(--c-border); background: var(--c-bg-elevated);
  color: var(--c-text-secondary); transition: all 0.15s;
}
.example-chip:hover { border-color: var(--c-accent-border); color: var(--c-accent-hover); }

/* ═══════════════════════════ Modal ═══════════════════════════ */
.modal-overlay {
  position: fixed; inset: 0; z-index: 100;
  background: rgba(0,0,0,0.5); display: flex; align-items: center; justify-content: center;
  backdrop-filter: blur(4px);
}
.modal-card {
  width: 560px; max-width: 90vw; border-radius: 16px;
  background: var(--c-bg-card); border: 1px solid var(--c-border);
  overflow: hidden; animation: modalIn 0.2s ease;
}
@keyframes modalIn {
  from { opacity: 0; transform: scale(0.95) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}
.modal-header {
  display: flex; align-items: center; justify-content: space-between;
  padding: 16px 20px; border-bottom: 1px solid var(--c-border-light);
}
.modal-title { font-size: 15px; font-weight: 600; color: var(--c-text); }
.modal-thumb { width: 100%; height: 280px; overflow: hidden; }
.modal-thumb img { width: 100%; height: 100%; object-fit: cover; display: block; }
.modal-body { padding: 20px; }
.modal-desc { font-size: 13px; color: var(--c-text-secondary); line-height: 1.6; margin-bottom: 16px; }
.modal-detail-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
.detail-item { display: flex; flex-direction: column; gap: 2px; }
.detail-label { font-size: 11px; color: var(--c-text-muted); font-weight: 500; }
.detail-value { font-size: 13px; color: var(--c-text); font-weight: 500; }
.detail-value.severity-warning { color: var(--c-amber); }
.detail-value.severity-critical { color: var(--c-red); }
.detail-value.severity-info { color: var(--c-blue-text); }
.modal-footer {
  padding: 12px 20px; border-top: 1px solid var(--c-border-light);
  display: flex; justify-content: flex-end;
}

/* ═══════════════════════════ Responsive ═══════════════════════════ */
@media (max-width: 1024px) {
  .topnav-links { display: none; }
  .nav-divider { display: none; }
  .event-card { flex-direction: column; }
  .event-thumb { width: 100%; height: 180px; }
  .event-action { padding-top: 0; }
  .event-time { margin-left: 0; }
  .search-bar-wrap { flex-direction: column; }
  .search-icon-left { display: none; }
  .search-input { padding: 12px 14px; }
  .btn-search { width: calc(100% - 8px); margin: 0 4px 4px; justify-content: center; }
}
</style>
