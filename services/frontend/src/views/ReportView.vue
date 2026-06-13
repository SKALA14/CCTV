<template>
  <div class="p-4 max-w-3xl mx-auto">
    <div class="flex items-center justify-between mb-4">
      <h1 class="text-lg font-bold" style="color: var(--text-primary);">안전 리포트</h1>
      <div class="flex gap-1">
        <button v-for="d in [7, 30]" :key="d" @click="days = d; load()"
          class="text-xs px-3 py-1.5 rounded-lg transition-colors"
          :style="days === d
            ? 'background: var(--blue); color: #fff;'
            : 'background: var(--bg-elevated); color: var(--text-muted); border: 1px solid var(--border);'">
          최근 {{ d }}일
        </button>
      </div>
    </div>

    <div v-if="loading" class="flex justify-center py-12">
      <div class="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>

    <template v-else-if="data">
      <!-- 총계 -->
      <div class="rounded-2xl p-5 mb-4" style="background: var(--bg-card); border: 1px solid var(--border);">
        <p class="text-xs" style="color: var(--text-muted);">최근 {{ data.days }}일 누적 이벤트</p>
        <p class="text-3xl font-bold mt-1" style="color: var(--text-primary);">{{ data.total }}<span class="text-sm font-normal ml-1" style="color: var(--text-muted);">건</span></p>
      </div>

      <!-- 위험도 분포 (정상 제외) -->
      <div class="rounded-2xl p-5 mb-4" style="background: var(--bg-card); border: 1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color: var(--text-primary);">위험도 분포</h2>
        <div v-for="lvl in dangerOrder" :key="lvl" class="flex items-center gap-2 mb-1.5">
          <span class="text-xs w-12" style="color: var(--text-muted);">{{ dangerLabel[lvl] }}</span>
          <div class="flex-1 h-3 rounded-full overflow-hidden" style="background: var(--bg-elevated);">
            <div class="h-full rounded-full" :style="`width: ${barPct(data.danger_breakdown[lvl])}%; background: ${dangerColor[lvl]};`"></div>
          </div>
          <span class="text-xs w-8 text-right" style="color: var(--text-primary);">{{ data.danger_breakdown[lvl] || 0 }}</span>
        </div>
      </div>

      <!-- 일자별 추이 -->
      <div class="rounded-2xl p-5 mb-4" style="background: var(--bg-card); border: 1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color: var(--text-primary);">일자별 추이</h2>
        <div class="flex items-end gap-1" style="height: 90px; overflow: hidden;">
          <div v-for="(d, i) in data.by_day" :key="i" class="flex-1 flex flex-col items-center justify-end gap-0.5">
            <div class="w-full rounded-t" :style="`height: ${barH(d.count, dayMax)}px; background: var(--blue); min-height: 2px;`" :title="`${d.date}: ${d.count}건`"></div>
          </div>
        </div>
        <div class="flex items-start gap-1 mt-1">
          <div v-for="(d, i) in data.by_day" :key="i" class="flex-1 flex flex-col items-center gap-0.5">
            <span class="text-[8px] leading-none" style="color: var(--text-subtle);">{{ d.date.slice(3) }}</span>
            <span class="text-[8px] leading-none" style="color: var(--text-muted);">{{ d.count }}건</span>
          </div>
        </div>
      </div>

      <!-- 시간대별 -->
      <div class="rounded-2xl p-5 mb-4" style="background: var(--bg-card); border: 1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color: var(--text-primary);">시간대별 (0–23시)</h2>
        <div class="flex items-end gap-px" style="height: 60px; overflow: hidden;">
          <div v-for="h in data.by_hour" :key="h.hour" class="flex-1 rounded-t"
            :style="`height: ${barH(h.count, hourMax)}px; background: var(--orange); min-height: 2px; opacity: ${h.count ? 1 : 0.25};`"
            :title="`${h.hour}시: ${h.count}건`"></div>
        </div>
        <div class="flex gap-px mt-1">
          <div v-for="h in data.by_hour" :key="h.hour" class="flex-1 text-center">
            <span class="text-[7px]" style="color: var(--text-subtle);">{{ h.hour }}</span>
          </div>
        </div>
      </div>

      <!-- 카메라 당 건수 -->
      <div class="rounded-2xl p-5" style="background: var(--bg-card); border: 1px solid var(--border);">
        <h2 class="text-sm font-semibold mb-3" style="color: var(--text-primary);">카메라 당 건수</h2>
        <div v-if="data.top_cameras.length === 0" class="text-xs" style="color: var(--text-subtle);">데이터 없음</div>
        <div v-for="(c, i) in data.top_cameras" :key="i" class="flex items-center gap-2 mb-1.5">
          <span class="text-xs w-4" style="color: var(--text-subtle);">{{ i + 1 }}</span>
          <span class="text-sm flex-1 truncate" style="color: var(--text-primary);">{{ c.camera }}</span>
          <span class="text-xs" style="color: var(--text-muted);">{{ c.count }}건</span>
        </div>
      </div>
    </template>
  </div>
</template>

<script setup>
import { ref, computed, onMounted } from 'vue'
import { getReportSummary } from '../api/reports.js'

const days = ref(7)
const data = ref(null)
const loading = ref(true)

const dangerOrder = ['critical', 'high', 'low']
const dangerLabel = { critical: '심각', high: '높음', low: '낮음' }
const dangerColor = { critical: '#b91c1c', high: '#dc2626', low: '#16a34a' }

const dangerMax = computed(() => Math.max(1, ...dangerOrder.map(l => data.value?.danger_breakdown[l] || 0)))
const dayMax    = computed(() => Math.max(1, ...(data.value?.by_day  || []).map(d => d.count)))
const hourMax   = computed(() => Math.max(1, ...(data.value?.by_hour || []).map(h => h.count)))

function barPct(n) { return Math.round(((n || 0) / dangerMax.value) * 100) }
function barH(n, max) {
  const maxPx = max === dayMax.value ? 84 : 56
  return Math.round(((n || 0) / max) * maxPx)
}

async function load() {
  loading.value = true
  try { data.value = await getReportSummary(days.value) } finally { loading.value = false }
}
onMounted(load)
</script>
