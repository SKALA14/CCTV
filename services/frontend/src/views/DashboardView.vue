<template>
  <div class="h-full">
    <ChannelGrid
      :slots="slots"
      @add="openAddModal"
      @edit="openEditModal"
      @remove="handleRemove"
    />
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
import { ref, computed, inject, watch } from 'vue'
import ChannelGrid from '../components/dashboard/ChannelGrid.vue'
import AddChannelModal from '../components/dashboard/AddChannelModal.vue'
import { useChannels } from '../composables/useChannels.js'
import { postChannel, deleteChannel } from '../api/channels.js'

const { slots, addChannel, updateChannel, removeChannel } = useChannels()

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
  } else {
    addChannel(data.slot, data)
    postChannel({ slot: data.slot, camera_id: `cam${data.slot}`, ...data }).catch(console.error)
  }
  closeModal()
}

function handleRemove(slot) {
  if (confirm('채널을 삭제하시겠습니까?')) {
    const ch = slots.value[slot]
    removeChannel(slot)
    if (ch) deleteChannel(ch.camera_id)
  }
}
</script>