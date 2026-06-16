<!-- 채널 그리드 — 4개 슬롯 격자 배치 -->
<template>
  <div class="grid grid-cols-2 grid-rows-2 gap-3 p-4" style="height: 100%;">
    <template v-for="i in 4" :key="i - 1">
      <ChannelCard
        v-if="slots[i - 1]"
        :channel="slots[i - 1]"
        :can-edit="canEdit"
        @edit="$emit('edit', slots[i - 1])"
        @remove="$emit('remove', i - 1)"
      />
      <div
        v-else
        class="add-slot"
        :class="canEdit ? '' : 'opacity-40 cursor-not-allowed'"
        @click="canEdit && $emit('add', i - 1)"
      >
        <span class="text-5xl font-thin text-[#3a3a3c]">+</span>
        <span class="text-sm text-[#636366] mt-1">{{ canEdit ? '채널 추가' : '읽기 전용' }}</span>
        <span class="text-xs text-[#48484a]">슬롯 {{ i - 1 }}</span>
      </div>
    </template>
  </div>
</template>

<script setup>
import ChannelCard from './ChannelCard.vue'

defineProps({ slots: Array, canEdit: { type: Boolean, default: false } })
defineEmits(['add', 'edit', 'remove'])
</script>
