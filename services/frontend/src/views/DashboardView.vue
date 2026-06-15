<template>
  <div class="h-full flex flex-col">
    <!-- 헤더 바 -->
    <header
      class="flex items-center justify-between px-4 flex-shrink-0"
      style="height: 44px; border-bottom: 1px solid var(--border); background: var(--bg-card);"
    >
      <div class="flex items-center gap-3">
        <div class="flex items-center gap-2">
          <svg width="22" height="26" viewBox="0 0 28 32" fill="none">
            <circle cx="14" cy="13" r="13" fill="#1e293b" stroke="#334155" stroke-width="0.8"/>
            <circle cx="14" cy="13" r="10" fill="#e2e8f0"/>
            <circle cx="14" cy="13" r="8" fill="#1e293b"/>
            <circle cx="14" cy="13" r="5" fill="#f1f5f9"/>
            <circle cx="14" cy="13" r="3.2" fill="#0f172a"/>
            <circle cx="11.8" cy="10.8" r="1.3" fill="white" opacity="0.85"/>
            <circle cx="15.5" cy="14" r="0.6" fill="white" opacity="0.6"/>
            <ellipse cx="14" cy="28" rx="6.5" ry="1.6" fill="#1e293b" stroke="#334155" stroke-width="0.8"/>
            <rect x="11.5" y="25.5" width="5" height="3.5" rx="0.5" fill="#1e293b" stroke="#334155" stroke-width="0.8"/>
          </svg>
          <span style="font-size:18px; font-weight:700; letter-spacing:4px; color:#c0513a;">SIREN</span>
        </div>
        <span
          class="flex items-center gap-1.5 text-xs px-2 py-0.5 rounded"
          style="background: var(--bg-elevated); color: var(--text-muted);"
        >
          <span class="w-1.5 h-1.5 rounded-full" :style="activeCount > 0 ? 'background:#22c55e' : 'background:#48484a'"></span>
          {{ activeCount }} / 4 채널
        </span>
      </div>

      <div class="text-sm font-mono" style="color: var(--text-primary);">{{ clock }}</div>

      <div class="flex items-center gap-1">
        <button
          class="flex items-center gap-2 px-2.5 py-1 rounded-lg transition-colors"
          style="color: var(--text-muted);"
          title="콘솔(검색·설정)을 새 창으로 열기"
          @click="openConsole"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <circle cx="12" cy="12" r="3"/>
            <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"/>
          </svg>
          <span class="text-xs">콘솔</span>
        </button>

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
      </div>
    </header>

    <!-- 바디: 채널 그리드 + 알림 히스토리 패널 -->
    <div class="flex-1 min-h-0 relative">
      <ChannelGrid
        :slots="slots"
        :can-edit="canEdit"
        @add="openAddModal"
        @edit="openEditModal"
        @remove="handleRemove"
      />
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
import { ref, computed, onMounted, onUnmounted } from 'vue'
import { storeToRefs } from 'pinia'
import ChannelGrid from '../components/dashboard/ChannelGrid.vue'
import AddChannelModal from '../components/dashboard/AddChannelModal.vue'
import EventPanel from '../components/dashboard/EventPanel.vue'
import { useChannels } from '../composables/useChannels.js'
import { useEventStore } from '../stores/eventStore.js'
import { postChannel, putChannel, deleteChannel } from '../api/channels.js'
import { useAuthStore } from '../stores/authStore.js'

const authStore = useAuthStore()
// 채널 편집은 admin 전용 — user는 불가
const canEdit = computed(() => authStore.user?.role === 'admin')

// 콘솔(검색·설정)을 별도 창으로 — 관제 화면은 그대로 유지. 같은 창 이름이라 재클릭 시 기존 창 재사용.
function openConsole() {
  window.open('/search', 'cctv-console', 'width=1440,height=900,left=120,top=80')
}

const { slots, addChannel, updateChannel, removeChannel } = useChannels()

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

async function handleSubmit(data) {
  if (editingChannel.value) {
    updateChannel(data.slot, data)
    putChannel(data.channelName, data).catch(console.error)
  } else {
    // 백엔드 응답의 mtxPath(접두사 포함 MediaMTX 경로)를 합쳐 등록 직후에도 영상이 뜨게 함
    let mtxPath = null
    try { mtxPath = (await postChannel(data))?.mtxPath } catch (e) { console.error(e) }
    addChannel(data.slot, { ...data, mtxPath })
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