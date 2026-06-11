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
          <span class="text-[10px] px-2 py-0.5 rounded-full" style="background: var(--bg-elevated); color: var(--text-muted);">
            점검 {{ z.static.length + z.dynamic.length }}항목
          </span>
        </div>
        <div v-if="z.static.length" class="mb-2">
          <p class="text-[10px] font-medium mb-1" style="color: var(--text-subtle);">정적 {{ z.static.length }}</p>
          <ul class="space-y-0.5">
            <li v-for="(it, i) in z.static.slice(0, 3)" :key="i" class="text-xs truncate" style="color: var(--text-muted);">· {{ it }}</li>
          </ul>
        </div>
        <div v-if="z.dynamic.length">
          <p class="text-[10px] font-medium mb-1" style="color: var(--text-subtle);">동적 {{ z.dynamic.length }}</p>
          <ul class="space-y-0.5">
            <li v-for="(it, i) in z.dynamic.slice(0, 3)" :key="i" class="text-xs truncate" style="color: var(--text-muted);">· {{ it }}</li>
          </ul>
        </div>
        <p v-if="!z.static.length && !z.dynamic.length" class="text-xs" style="color: var(--text-subtle);">점검 항목 미설정</p>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { fetchZones, fetchChecklist } from '../api/manuals.js'

const zones = ref([])
const loading = ref(true)

onMounted(async () => {
  try {
    const [names, cl] = await Promise.all([fetchZones(), fetchChecklist()])
    const byName = {}
    for (const z of (cl.zones || [])) byName[z.zone] = z
    zones.value = (names || []).map(name => ({
      zone: name,
      static: byName[name]?.static || [],
      dynamic: byName[name]?.dynamic || [],
    }))
  } catch { zones.value = [] } finally {
    loading.value = false
  }
})
</script>
