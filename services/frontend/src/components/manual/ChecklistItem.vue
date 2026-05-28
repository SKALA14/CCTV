<template>
  <div
    class="flex items-start gap-2 px-3 py-2 rounded-lg group"
    style="background: var(--bg-elevated);"
  >
    <p class="flex-1 text-sm leading-relaxed" style="color: var(--text-primary);">
      {{ item }}
    </p>
    <button
      class="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-xs px-1.5 py-0.5 rounded"
      style="color: var(--red); border: 1px solid var(--border);"
      @click="$emit('remove')"
    >
      삭제
    </button>
  </div>
</template>

<script setup>
defineProps({ item: { type: String, required: true } })
defineEmits(['remove'])
</script>
