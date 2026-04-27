<template>
  <div class="flex flex-wrap gap-2">
    <span
      class="px-3 py-1 rounded-full text-sm cursor-pointer transition-colors select-none"
      :class="modelValue === null ? 'bg-blue-600 border-blue-600 text-white' : ''"
      :style="modelValue !== null ? 'border: 1px solid var(--border); color: var(--text-muted);' : 'border: 1px solid transparent;'"
      @click="emit('update:modelValue', null)"
    >전체 채널</span>
    <span
      v-for="ch in channels"
      :key="ch.id"
      class="px-3 py-1 rounded-full text-sm cursor-pointer transition-colors select-none"
      :class="modelValue === ch.id ? 'bg-blue-600 border-blue-600 text-white' : ''"
      :style="modelValue !== ch.id ? 'border: 1px solid var(--border); color: var(--text-muted);' : 'border: 1px solid transparent;'"
      @click="emit('update:modelValue', ch.id)"
    >{{ ch.name }}</span>
  </div>
</template>

<script setup>
defineProps({ channels: Array, modelValue: { default: null } })
const emit = defineEmits(['update:modelValue'])
</script>
