<template>
  <div class="grid grid-cols-2 grid-rows-2 gap-3 p-4" style="height: calc(100vh - 56px);">
    <template v-for="i in 4" :key="i - 1">
      <ChannelCard
        v-if="slots[i - 1]"
        :channel="slots[i - 1]"
        @edit="$emit('edit', slots[i - 1])"
        @remove="$emit('remove', i - 1)"
      />
      <div
        v-else
        class="add-slot"
        @click="$emit('add', i - 1)"
      >
        <span class="text-5xl font-thin text-[#3a3a3c]">+</span>
        <span class="text-sm text-[#636366] mt-1">채널 추가</span>
        <span class="text-xs text-[#48484a]">슬롯 {{ i - 1 }}</span>
      </div>
    </template>
  </div>
</template>

<script setup>
import ChannelCard from './ChannelCard.vue'

defineProps({ slots: Array })
defineEmits(['add', 'edit', 'remove'])
</script>