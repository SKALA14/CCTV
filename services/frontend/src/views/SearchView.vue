<template>
  <div class="p-4 max-w-3xl mx-auto">
    <div class="mb-4 space-y-3">
      <!-- 현장 필터 — superadmin 전용 -->
      <select
        v-if="isSuperadmin"
        v-model="selectedSiteId"
        class="app-select w-full px-4 py-2.5 rounded-xl text-sm"
      >
        <option :value="null">전체 현장</option>
        <option v-for="s in sites" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>

      <SearchBar @search="handleSearch" />

      <!-- 빠른 날짜 필터 버튼 -->
      <div class="flex flex-wrap gap-2">
        <span
          v-for="f in QUICK_FILTERS"
          :key="f.key"
          class="px-3 py-1 rounded-full text-sm cursor-pointer transition-colors select-none"
          :class="selectedQuickFilter === f.key ? 'bg-blue-600 text-white' : ''"
          :style="selectedQuickFilter !== f.key
            ? 'border: 1px solid var(--border); color: var(--text-muted);'
            : 'border: 1px solid transparent;'"
          @click="handleQuickFilter(f.key)"
        >{{ f.label }}</span>
      </div>

      <!-- 자연어 필터 칩 -->
      <div
        v-if="appliedFilter && !selectedQuickFilter"
        class="flex items-center gap-2"
      >
        <span class="text-xs" style="color: var(--text-muted);">검색어에서 감지:</span>
        <span
          class="flex items-center gap-1.5 px-2.5 py-1 rounded-full text-xs"
          style="background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);"
        >
          {{ appliedFilter }}
          <button
            class="ml-0.5 leading-none"
            style="color: var(--text-muted);"
            @click="clearAppliedFilter"
          >×</button>
        </span>
      </div>

      <ChannelFilter
        :channels="channels"
        v-model="selectedChannelId"
      />
    </div>

    <ResultList
      :events="events"
      :loading="loading"
      :error="error"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import SearchBar     from '../components/search/SearchBar.vue'
import ChannelFilter from '../components/search/ChannelFilter.vue'
import ResultList    from '../components/search/ResultList.vue'
import { useEvents }    from '../composables/useEvents.js'
import { useChannels }  from '../composables/useChannels.js'
import { useEventStore } from '../stores/eventStore.js'
import { getSites }      from '../api/sites.js'
import { useAuthStore }  from '../stores/authStore.js'

const { events, loading, error, appliedFilter, load, search } = useEvents()
const { slots }   = useChannels()
const channels    = computed(() => slots.value.filter(Boolean))
const eventStore  = useEventStore()

const selectedChannelId   = ref(null)
const selectedSiteId      = ref(null)
const sites               = ref([])
const authStore           = useAuthStore()
const isSuperadmin        = computed(() => authStore.isSuperadmin)
const lastQuery           = ref('')
const selectedQuickFilter = ref(null)

onMounted(async () => {
  await load()
  if (isSuperadmin.value) {
    try {
      sites.value = await getSites()
    } catch (e) {
      console.error('[SearchView] 현장 목록 로드 실패:', e)
    }
  }
})

const QUICK_FILTERS = [
  { key: 'today',      label: '오늘' },
  { key: 'this_week',  label: '이번 주' },
  { key: 'last_7',     label: '지난 7일' },
  { key: 'this_month', label: '이번 달' },
]

function getQuickFilterDates(key) {
  const now     = new Date()
  const dayStart = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).toISOString()

  if (key === 'today') {
    return { startDate: dayStart(now), endDate: now.toISOString() }
  }
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
  await search(
    query,
    selectedChannelId.value,
    startDate,
    endDate,
    skipTimeParse,
    selectedSiteId.value,
  )
  eventStore.setSearchResults(events.value)
}

async function handleQuickFilter(key) {
  if (selectedQuickFilter.value === key) {
    selectedQuickFilter.value = null
    if (lastQuery.value) await handleSearch(lastQuery.value)
    return
  }
  selectedQuickFilter.value = key
  if (lastQuery.value) {
    const { startDate, endDate } = getQuickFilterDates(key)
    await handleSearch(lastQuery.value, startDate, endDate)
  }
}

async function clearAppliedFilter() {
  await handleSearch(lastQuery.value, null, null, true)
}

watch(selectedChannelId, async () => {
  if (lastQuery.value) {
    const dates = selectedQuickFilter.value
      ? getQuickFilterDates(selectedQuickFilter.value)
      : { startDate: null, endDate: null }
    await handleSearch(lastQuery.value, dates.startDate, dates.endDate)
  } else {
    const params = selectedChannelId.value ? { channel_id: selectedChannelId.value } : {}
    await load(params)
  }
})

watch(selectedSiteId, async () => {
  if (lastQuery.value) {
    const dates = selectedQuickFilter.value
      ? getQuickFilterDates(selectedQuickFilter.value)
      : { startDate: null, endDate: null }
    await handleSearch(lastQuery.value, dates.startDate, dates.endDate)
  } else {
    await load({ site_id: selectedSiteId.value || undefined })
  }
})
</script>
