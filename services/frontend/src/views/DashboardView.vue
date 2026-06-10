<template>
  <div class="h-full flex flex-col">
    <!-- 헤더 바 -->
    <header
      class="flex items-center justify-between px-4 flex-shrink-0"
      style="height: 44px; border-bottom: 1px solid var(--border); background: var(--bg-card);"
    >
      <div class="flex items-center gap-3">
        <span class="text-xs font-bold tracking-widest uppercase" style="color: var(--text-primary);">AI CCTV</span>
        <span
          class="flex items-center gap-1.5 text-xs px-2 py-0.5 rounded"
          style="background: var(--bg-elevated); color: var(--text-muted);"
        >
          <span class="w-1.5 h-1.5 rounded-full" :style="activeCount > 0 ? 'background:#22c55e' : 'background:#48484a'"></span>
          {{ activeCount }} / 4 채널
        </span>
      </div>

      <div class="text-sm font-mono" style="color: var(--text-primary);">{{ clock }}</div>

      <button
        class="flex items-center gap-2 px-2.5 py-1 rounded-lg transition-colors"
        :style="panelOpen
          ? 'background: var(--bg-elevated); color: var(--text-primary);'
          : 'color: var(--text-muted);'"
        @click="panelOpen = !panelOpen"
      >
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
          <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
        </svg>
        <span class="text-xs">알림</span>
        <span
          v-if="historyCount > 0"
          class="text-[10px] font-semibold px-1.5 py-px rounded"
          style="background: rgba(220,38,38,0.15); color: #dc2626;"
        >{{ historyCount }}</span>
      </button>
    </header>

    <!-- superadmin 현장 선택 (읽기 전용 뷰) -->
    <div v-if="isSuperadmin" class="px-4 pt-3">
      <select
        v-model="selectedSiteId"
        class="w-full max-w-xs px-3 py-2 rounded-xl text-sm"
        style="background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);"
      >
        <option :value="null">현장을 선택하세요</option>
        <option v-for="s in sites" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
    </div>

    <!-- 바디: 채널 그리드 + 알림 히스토리 패널 -->
    <div class="flex flex-1 min-h-0">
      <div class="flex-1 min-w-0">
        <ChannelGrid
          :slots="slots"
          :can-edit="canEdit"
          @add="openAddModal"
          @edit="openEditModal"
          @remove="handleRemove"
        />
      </div>
      <EventPanel v-if="panelOpen" />
    </div>

    <AddChannelModal
      v-if="showModal"
      :slot-index="activeSlot"
      :initial="editingChannel"
      :existing-names="existingNames"
      @close="closeModal"
      @submit="handleSubmit"
    />
  </div>
</template>

<script setup>
import { ref, computed, inject, watch, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import ChannelGrid from '../components/dashboard/ChannelGrid.vue'
import AddChannelModal from '../components/dashboard/AddChannelModal.vue'
import EventPanel from '../components/dashboard/EventPanel.vue'
import { useChannels } from '../composables/useChannels.js'
import { useEventStore } from '../stores/eventStore.js'
import { getChannels, postChannel, putChannel, deleteChannel } from '../api/channels.js'
import { useAuthStore } from '../stores/authStore.js'
import { getSites } from '../api/sites.js'
import { useChannelStore } from '../stores/channelStore.js'

const authStore = useAuthStore()
// 채널 편집은 admin 전용 — superadmin은 읽기 전용(RBAC 스펙), viewer도 불가
const canEdit = computed(() => authStore.user?.role === 'admin')

const isSuperadmin = computed(() => authStore.isSuperadmin)
const sites = ref([])
const selectedSiteId = ref(null)
const channelStore = useChannelStore()

// 사용자 로드 이후 superadmin이면 현장 목록 적재
// - DashboardView는 App.vue에 상시 마운트되어 setup 시점엔 user가 아직 null일 수 있음(새로고침)
//   → user를 watch(immediate)해 로드 시점을 맞춘다
watch(() => authStore.user, (u) => {
  if (u?.role === 'superadmin' && sites.value.length === 0) {
    getSites().then(s => { sites.value = s }).catch(e => console.warn('현장 로드 실패:', e.message))
  }
}, { immediate: true })

// 현장 전환 — 늦게 도착한 이전 요청이 슬롯을 오염시키지 않도록 시퀀스 가드
let loadSeq = 0
watch(selectedSiteId, async (sid) => {
  const seq = ++loadSeq
  channelStore.resetSlots()
  if (!sid) return
  try {
    const res = await getChannels(sid)
    if (seq !== loadSeq) return   // 더 최신 요청이 진행 중이면 폐기
    res.data.forEach(ch => {
      if (channelStore.slots[ch.slot] === null) channelStore.addChannel(ch.slot, ch)
    })
  } catch (e) {
    console.warn('superadmin 채널 로드 실패:', e.message)
  }
})

const { slots, addChannel, updateChannel, removeChannel } = useChannels()

// 헤더 바: 활성 채널 수 · 알림 패널 토글 · 라이브 시계
const eventStore = useEventStore()
const { notifHistory } = storeToRefs(eventStore)
const activeCount = computed(() => slots.value.filter(Boolean).length)
const historyCount = computed(() => notifHistory.value.length)
const panelOpen = ref(false)

const clock = ref('')
let clockTimer = null
function updateClock() {
  clock.value = new Date().toLocaleTimeString('ko-KR', { hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false })
}
onMounted(() => { updateClock(); clockTimer = setInterval(updateClock, 1000) })
onUnmounted(() => { if (clockTimer) clearInterval(clockTimer) })

const showModal = ref(false)
const editingChannel = ref(null)
const activeSlot = ref(0)

// 수정 중인 슬롯 제외한 등록된 채널명 목록 (중복 체크용)
const existingNames = computed(() =>
  slots.value
    .filter((s, i) => s !== null && i !== activeSlot.value)
    .map(s => s.name)
)

// App.vue 상단 바의 "+ 채널 추가" 버튼 신호 수신 — 빈 슬롯 중 첫 번째에 등록
const addModalSignal = inject('addModalSignal', ref(false))
watch(addModalSignal, (v) => {
  if (v) {
    if (!canEdit.value) { addModalSignal.value = false; return }
    const firstEmpty = slots.value.findIndex(s => s === null)
    if (firstEmpty === -1) {
      alert('모든 슬롯이 사용 중입니다. 기존 채널을 삭제 후 추가해주세요.')
    } else {
      openAddModal(firstEmpty)
    }
    addModalSignal.value = false
  }
})

function openAddModal(slot) {
  activeSlot.value = slot
  editingChannel.value = null
  showModal.value = true
}

function openEditModal(channel) {
  activeSlot.value = channel.slot
  editingChannel.value = channel
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingChannel.value = null
}

function handleSubmit(data) {
  if (editingChannel.value) {
    updateChannel(data.slot, data)
    putChannel(data.channelName, data).catch(console.error)
  } else {
    addChannel(data.slot, data)
    postChannel(data).catch(console.error)
  }
  closeModal()
}

function handleRemove(slot) {
  if (confirm('채널을 삭제하시겠습니까?')) {
    const ch = slots.value[slot]
    removeChannel(slot)
    if (ch) deleteChannel(ch.channelName)
  }
}
</script>