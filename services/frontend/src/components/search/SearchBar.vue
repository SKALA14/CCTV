<template>
  <div class="flex gap-2">
    <input
      v-model="query"
      type="text"
      placeholder="예: 지난주 안전모 미착용 장면, 어제 오후 화재 감지"
      class="flex-1 h-11 px-4 rounded-xl text-sm focus:outline-none focus:border-blue-500 transition-colors"
      style="background: var(--bg-card); border: 1px solid var(--border); color: var(--text-primary);"
      @keyup.enter="emit('search', query)"
    />
    <button
      class="h-11 px-5 rounded-xl text-sm transition-colors"
      style="background: var(--bg-card); border: 1px solid var(--border); color: var(--text-primary);"
      @mouseover="e => e.currentTarget.style.background = 'var(--bg-elevated)'"
      @mouseleave="e => e.currentTarget.style.background = 'var(--bg-card)'"
      @click="emit('search', query)"
    >
      검색
    </button>
  </div>
</template>

<script setup>
import { ref } from 'vue'

const query = ref('')
const emit = defineEmits(['search'])
</script>
