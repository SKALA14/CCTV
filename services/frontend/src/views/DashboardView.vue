<template>
  <div class="h-full">
    <ChannelGrid
      :channels="channels"
      @add="openAddModal"
      @edit="openEditModal"
      @remove="handleRemove"
    />
    <AddChannelModal
      v-if="showModal"
      :initial="editingChannel"
      @close="closeModal"
      @submit="handleSubmit"
    />
  </div>
</template>

<script setup>
import { ref, inject, watch } from 'vue'
import ChannelGrid from '../components/dashboard/ChannelGrid.vue'
import AddChannelModal from '../components/dashboard/AddChannelModal.vue'
import { useChannels } from '../composables/useChannels.js'

const { channels, addChannel, updateChannel, removeChannel } = useChannels()

const showModal = ref(false)
const editingChannel = ref(null)

// App.vue 상단 바의 "+ 채널 추가" 버튼 신호 수신
const addModalSignal = inject('addModalSignal', ref(false))
watch(addModalSignal, (v) => {
  if (v) {
    openAddModal()
    addModalSignal.value = false
  }
})

function openAddModal() {
  editingChannel.value = null
  showModal.value = true
}

function openEditModal(channel) {
  editingChannel.value = channel
  showModal.value = true
}

function closeModal() {
  showModal.value = false
  editingChannel.value = null
}

function handleSubmit(data) {
  if (data.id) {
    updateChannel(data.id, data)
  } else {
    addChannel(data)
  }
  closeModal()
}

function handleRemove(id) {
  if (confirm('채널을 삭제하시겠습니까?')) {
    removeChannel(id)
  }
}
</script>
