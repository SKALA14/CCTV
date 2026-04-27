<template>
  <div class="grid grid-cols-2 grid-rows-2 gap-3 p-4" style="height: calc(100vh - 56px);">
    <ChannelCard
      v-for="ch in channels"
      :key="ch.id"
      :channel="ch"
      @edit="$emit('edit', ch)"
      @remove="$emit('remove', ch.id)"
    />
    <div
      v-if="channels.length < 4"
      class="add-slot"
      @click="$emit('add')"
    >
      <span class="text-5xl font-thin text-[#3a3a3c]">+</span>
      <span class="text-sm text-[#636366] mt-1">채널 추가</span>
      <span class="text-xs text-[#48484a]">최대 4채널</span>
    </div>
  </div>
</template>

<script setup>
import ChannelCard from './ChannelCard.vue'

defineProps({ channels: Array })
defineEmits(['add', 'edit', 'remove'])
</script>
