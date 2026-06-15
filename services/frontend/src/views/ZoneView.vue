<template>
  <div class="p-4 max-w-3xl mx-auto">
    <h1 class="text-lg font-bold mb-1" style="color: var(--text-primary);">구역</h1>
    <p class="text-xs mb-4" style="color: var(--text-subtle);">현장 구역별 안전 점검 항목 현황입니다.</p>

    <div v-if="loading" class="flex justify-center py-12">
      <div class="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
    <div v-else-if="zones.length === 0" class="text-center py-16 text-sm" style="color: var(--text-subtle);">
      등록된 구역이 없습니다. 메뉴얼 탭에서 구역을 등록하세요.
    </div>
    <div v-else class="grid grid-cols-1 sm:grid-cols-2 gap-3">
      <div v-for="z in zones" :key="z.zone" class="rounded-2xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
        <div class="flex items-center justify-between mb-3">
          <h2 class="font-semibold text-sm" style="color: var(--text-primary);">{{ z.zone }}</h2>
          <span class="text-[10px] font-medium px-2 py-0.5 rounded-full" style="background: rgba(59,130,246,0.15); color: #60a5fa;">
            점검 {{ z.static.length + z.dynamic.length }}항목
          </span>
        </div>
        <div v-if="z.static.length" class="mb-3">
          <div class="flex items-center gap-1.5 mb-1.5">
            <span class="text-[10px] font-semibold" style="color: var(--text-subtle);">정적</span>
            <span class="text-[10px]" style="color: var(--text-subtle);">{{ z.static.length }}개</span>
          </div>
          <ul class="space-y-1">
            <li v-for="(it, i) in z.static" :key="i" class="text-xs leading-relaxed" style="color: var(--text-primary);">· {{ it }}</li>
          </ul>
        </div>
        <div v-if="z.static.length && z.dynamic.length" class="mb-3" style="border-top: 1px solid var(--border);"></div>
        <div v-if="z.dynamic.length">
          <div class="flex items-center gap-1.5 mb-1.5">
            <span class="text-[10px] font-semibold" style="color: var(--text-subtle);">동적</span>
            <span class="text-[10px]" style="color: var(--text-subtle);">{{ z.dynamic.length }}개</span>
          </div>
          <ul class="space-y-1">
            <li v-for="(it, i) in z.dynamic" :key="i" class="text-xs leading-relaxed" style="color: var(--text-primary);">· {{ it }}</li>
          </ul>
        </div>
        <p v-if="!z.static.length && !z.dynamic.length" class="text-xs" style="color: var(--text-subtle);">점검 항목 미설정</p>
      </div>
    </div>
  </div>
</template>

<script>
export default { name: 'ZoneView' }
</script>

<script setup>
import { onMounted, onActivated, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useManualStore } from '../stores/manualStore.js'
import { fetchZones, fetchChecklist } from '../api/manuals.js'

const store = useManualStore()
const { zoneViewData, zoneViewLoaded } = storeToRefs(store)

const zones = computed(() => zoneViewData.value)
const loading = computed(() => !zoneViewLoaded.value && zoneViewData.value.length === 0)

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
  } catch { zoneViewData.value = [] } finally {
    zoneViewLoaded.value = true
  }
}

onMounted(loadZones)
onActivated(loadZones)  // keep-alive로 복귀 시에도 zoneViewLoaded 초기화 감지
</script>
