<template>
  <div class="p-6 max-w-5xl mx-auto">
    <div class="flex items-center justify-between mb-5">
      <h1 class="text-lg font-bold" style="color: var(--text-primary);">시스템 현황</h1>
      <button
        class="text-xs px-3 py-1.5 rounded-lg"
        style="background: var(--bg-elevated); color: var(--text-muted); border: 1px solid var(--border);"
        @click="refreshAll"
      >새로고침</button>
    </div>

    <!-- 현장 요약 -->
    <h2 class="font-semibold text-sm mb-2" style="color: var(--text-primary);">현장 요약</h2>
    <div class="grid grid-cols-2 md:grid-cols-3 gap-3 mb-8">
      <div v-for="s in overview" :key="s.site_id"
        class="rounded-xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
        <p class="font-medium text-sm mb-2" style="color: var(--text-primary);">{{ s.name }}</p>
        <div class="text-xs space-y-1" style="color: var(--text-muted);">
          <div>카메라 <span class="tabular-nums">{{ s.camera_count }}</span>대</div>
          <div>계정 <span class="tabular-nums">{{ s.account_count }}</span>명</div>
          <button
            class="text-left hover:underline"
            style="color: var(--text-muted);"
            @click="openSiteEvents(s)"
          >오늘 이벤트 <span class="tabular-nums">{{ s.today_event_count }}</span>건 ›</button>
        </div>
      </div>
      <p v-if="!overview.length" class="text-sm col-span-full" style="color: var(--text-muted);">등록된 현장이 없습니다.</p>
    </div>

    <!-- CCTV 기기 상태 -->
    <h2 class="font-semibold text-sm mb-2" style="color: var(--text-primary);">CCTV 기기 상태</h2>
    <div class="rounded-xl overflow-hidden mb-8" style="border: 1px solid var(--border);">
      <table class="w-full text-sm">
        <thead>
          <tr style="background: var(--bg-elevated);">
            <th class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-muted);">현장</th>
            <th class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-muted);">카메라</th>
            <th class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-muted);">소스</th>
            <th class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-muted);">상태</th>
            <th class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-muted);">마지막 수신</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(d, i) in devices" :key="i" style="border-top: 1px solid var(--border);">
            <td class="px-4 py-2.5" style="color: var(--text-primary);">{{ d.site_name }}</td>
            <td class="px-4 py-2.5" style="color: var(--text-primary);">{{ d.camera_name }}</td>
            <td class="px-4 py-2.5" style="color: var(--text-muted);">{{ d.source_type }}</td>
            <td class="px-4 py-2.5">
              <span class="inline-flex items-center gap-1.5 text-xs">
                <span class="w-2 h-2 rounded-full" :style="d.online ? 'background:#22c55e;' : 'background:#6b7280;'"></span>
                {{ d.online ? '온라인' : '오프라인' }}
              </span>
            </td>
            <td class="px-4 py-2.5" style="color: var(--text-muted);">{{ fmt(d.last_seen) }}</td>
          </tr>
          <tr v-if="!devices.length"><td colspan="5" class="px-4 py-6 text-center text-sm" style="color: var(--text-muted);">등록된 카메라가 없습니다.</td></tr>
        </tbody>
      </table>
    </div>

    <!-- 계정 현황 -->
    <h2 class="font-semibold text-sm mb-2" style="color: var(--text-primary);">계정 현황</h2>
    <div class="rounded-xl overflow-hidden" style="border: 1px solid var(--border);">
      <table class="w-full text-sm">
        <thead>
          <tr style="background: var(--bg-elevated);">
            <th class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-muted);">현장</th>
            <th class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-muted);">username</th>
            <th class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-muted);">role</th>
            <th class="text-left px-4 py-2.5 font-semibold" style="color: var(--text-muted);">마지막 로그인</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="(a, i) in accounts" :key="i" style="border-top: 1px solid var(--border);">
            <td class="px-4 py-2.5" style="color: var(--text-muted);">{{ a.site_name || '—' }}</td>
            <td class="px-4 py-2.5" style="color: var(--text-primary);">
              {{ a.username }}
              <span v-if="a.must_change_password" class="ml-1 text-xs text-yellow-500">(초기)</span>
            </td>
            <td class="px-4 py-2.5"><span class="text-xs uppercase" style="color: var(--text-muted);">{{ a.role }}</span></td>
            <td class="px-4 py-2.5" style="color: var(--text-muted);">{{ fmt(a.last_login) }}</td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- 오늘 이벤트 상세 모달 -->
    <div
      v-if="eventsModal.open"
      class="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4"
      @click.self="eventsModal.open = false"
    >
      <div class="rounded-2xl w-full max-w-2xl max-h-[80vh] flex flex-col" style="background: var(--bg-card); border: 1px solid var(--border);">
        <div class="flex items-center justify-between px-5 py-3 flex-shrink-0" style="border-bottom: 1px solid var(--border);">
          <h3 class="font-bold text-sm" style="color: var(--text-primary);">{{ eventsModal.siteName }} — 오늘 이벤트</h3>
          <button class="text-sm" style="color: var(--text-muted);" @click="eventsModal.open = false">닫기</button>
        </div>
        <div class="flex-1 overflow-y-auto">
          <div v-if="eventsModal.loading" class="py-10 text-center text-sm" style="color: var(--text-muted);">불러오는 중...</div>
          <div v-else-if="!eventsModal.events.length" class="py-10 text-center text-sm" style="color: var(--text-muted);">오늘 발생한 이벤트가 없습니다.</div>
          <table v-else class="w-full text-sm">
            <thead>
              <tr style="background: var(--bg-elevated);">
                <th class="text-left px-4 py-2 font-semibold" style="color: var(--text-muted);">시각</th>
                <th class="text-left px-4 py-2 font-semibold" style="color: var(--text-muted);">카메라</th>
                <th class="text-left px-4 py-2 font-semibold" style="color: var(--text-muted);">유형</th>
                <th class="text-left px-4 py-2 font-semibold" style="color: var(--text-muted);">위험도</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="e in eventsModal.events" :key="e.event_id" style="border-top: 1px solid var(--border);">
                <td class="px-4 py-2 tabular-nums whitespace-nowrap" style="color: var(--text-primary);">{{ fmtTime(e.occurred_at) }}</td>
                <td class="px-4 py-2" style="color: var(--text-muted);">{{ e.camera_name }}</td>
                <td class="px-4 py-2" style="color: var(--text-primary);">
                  {{ e.event_type }}
                  <span v-if="e.pipeline === 'emergency'" class="ml-1 text-[9px] px-1 py-px rounded font-semibold" style="background: rgba(220,38,38,0.12); color:#dc2626;">EMG</span>
                </td>
                <td class="px-4 py-2"><span class="danger-badge" :class="e.danger_level">{{ e.danger_level }}</span></td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
import { getOverview, getDevices, getAccounts, getTodayEvents } from '../api/status.js'

const overview = ref([])
const devices  = ref([])
const accounts = ref([])
let timer = null

const eventsModal = ref({ open: false, loading: false, siteName: '', events: [] })

async function refreshAll() {
  try { overview.value = await getOverview() } catch (e) { console.warn(e?.message ?? e) }
  try { devices.value  = await getDevices() }  catch (e) { console.warn(e?.message ?? e) }
  try { accounts.value = await getAccounts() } catch (e) { console.warn(e?.message ?? e) }
}

async function openSiteEvents(s) {
  eventsModal.value = { open: true, loading: true, siteName: s.name, events: [] }
  try {
    eventsModal.value.events = await getTodayEvents(s.site_id)
  } catch (e) {
    console.warn(e?.message ?? e)
  } finally {
    eventsModal.value.loading = false
  }
}

function fmt(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleString('ko-KR', {
    month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit',
  })
}

function fmtTime(iso) {
  if (!iso) return '—'
  return new Date(iso).toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

onMounted(() => {
  refreshAll()
  timer = setInterval(refreshAll, 10000)
})
onUnmounted(() => { if (timer) clearInterval(timer) })
</script>
