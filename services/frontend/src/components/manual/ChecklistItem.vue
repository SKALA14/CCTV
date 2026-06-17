<!-- 체크리스트 개별 항목 — 보기/수정 -->
<template>
  <div
    class="flex items-start gap-2 px-3 py-2 rounded-lg group"
    :class="draggable && !editing ? 'cursor-grab active:cursor-grabbing' : ''"
    style="background: var(--bg-card); border: 1px solid var(--border);"
    :draggable="draggable && !editing"
    @dragstart="onDragStart"
  >
    <!-- 보기 모드 -->
    <template v-if="!editing">
      <p class="flex-1 text-sm leading-relaxed" style="color: var(--text-primary);">
        {{ item }}
      </p>
      <button
        class="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity p-1 rounded"
        style="color: var(--text-muted);"
        title="수정"
        @click="startEdit"
      >
        <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M12 20h9" />
          <path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z" />
        </svg>
      </button>
      <button
        class="flex-shrink-0 opacity-0 group-hover:opacity-100 transition-opacity text-xs px-1.5 py-0.5 rounded"
        style="color: var(--red); border: 1px solid var(--border);"
        @click="$emit('remove')"
      >
        삭제
      </button>
    </template>

    <!-- 편집 모드 -->
    <template v-else>
      <input
        ref="inputEl"
        v-model="draft"
        class="flex-1 text-sm px-2 py-1 rounded focus:outline-none"
        style="background: var(--bg-card); border: 1px solid #b6c77a; color: var(--text-primary);"
        @keydown.enter.prevent="save"
        @keydown.esc.prevent="cancel"
      />
      <button class="flex-shrink-0 text-xs px-2 py-1 rounded text-white" style="background: #77942e;" @click="save">저장</button>
      <button class="flex-shrink-0 text-xs px-1.5 py-1 rounded" style="color: var(--text-muted);" @click="cancel">취소</button>
    </template>
  </div>
</template>

<script setup>
import { ref, nextTick, onMounted } from 'vue'

const props = defineProps({
  item: { type: String, required: true },
  draggable: { type: Boolean, default: false },
})
const emit = defineEmits(['remove', 'update'])

const editing = ref(false)
const draft = ref(props.item)
const inputEl = ref(null)

function onDragStart(e) {
  e.dataTransfer.setData('text/plain', props.item)
  e.dataTransfer.effectAllowed = 'copy'
}

async function startEdit() {
  draft.value = props.item
  editing.value = true
  await nextTick()
  inputEl.value?.focus()
}

function save() {
  const v = draft.value.trim()
  if (!v) { emit('remove'); return }   // 비우고 저장하면 삭제
  emit('update', v)
  editing.value = false
}

function cancel() {
  if (!props.item.trim()) { emit('remove'); return }   // 빈 신규 항목 취소 → 제거
  draft.value = props.item
  editing.value = false
}

// 새로 추가된 빈 항목은 바로 편집 모드로 진입
onMounted(() => { if (!props.item.trim()) startEdit() })
</script>
