<!-- 체크리스트 검토 패널 (static/dynamic 2열) -->
<template>
  <div class="space-y-4">
    <!-- 드래그 힌트 -->
    <div class="flex items-center justify-between gap-3">
      <p class="text-[11px]" style="color: var(--text-subtle);">
      항목을 드래그해 오른쪽 구역에 추가할 수 있습니다.
      </p>
      <span
        v-if="loading"
        class="text-xs px-2 py-0.5 rounded-full whitespace-nowrap"
        style="background: #eef2df; color: #64731e; border: 1px solid #b6c77a;"
      >분석 중...</span>
    </div>

    <!-- 세로 리스트 -->
    <div class="space-y-4">
      <section class="rounded-xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
        <p class="text-xs font-medium mb-2" style="color: var(--text-muted);">Static (정적 상태)</p>
        <div class="space-y-1.5">
          <ChecklistItem
            v-for="(item, i) in localStatic"
            :key="i"
            :item="item"
            :draggable="true"
            @update="localStatic[i] = $event"
            @remove="localStatic.splice(i, 1)"
          />
          <button class="text-xs mt-0.5 font-medium" style="color: #64731e;" @click="localStatic.push('')">+ 항목 추가</button>
        </div>
      </section>
      <section class="rounded-xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
        <p class="text-xs font-medium mb-2" style="color: var(--text-muted);">Dynamic (행동·이벤트)</p>
        <div class="space-y-1.5">
          <ChecklistItem
            v-for="(item, i) in localDynamic"
            :key="i"
            :item="item"
            :draggable="true"
            @update="localDynamic[i] = $event"
            @remove="localDynamic.splice(i, 1)"
          />
          <button class="text-xs mt-0.5 font-medium" style="color: #64731e;" @click="localDynamic.push('')">+ 항목 추가</button>
        </div>
      </section>
    </div>

    <!-- 피드백 입력 -->
    <div class="space-y-2">
      <textarea
        v-model="feedback"
        placeholder="수정 요청 사항을 입력하세요 (예: '낙상 관련 항목을 더 구체적으로 작성해주세요')"
        rows="2"
        class="w-full px-3 py-2 rounded-lg text-sm resize-none focus:outline-none"
        style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-primary);"
        :disabled="loading"
      />
      <div class="flex gap-2 justify-end">
        <button
          class="px-3 py-1.5 rounded-lg text-sm transition-colors"
          style="background: var(--bg-elevated); color: var(--text-primary); border: 1px solid var(--border);"
          :disabled="loading || !feedback.trim()"
          @click="onRefine"
        >재생성</button>
        <button
          class="px-3 py-1.5 rounded-lg text-white text-sm transition-colors"
          style="background: #77942e;"
          :disabled="loading"
          @click="onConfirm"
        >확정</button>
      </div>
    </div>

    <!-- 에러 -->
    <p v-if="error" class="text-xs" style="color: var(--red);">{{ error }}</p>
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import ChecklistItem from './ChecklistItem.vue'

const props = defineProps({
  sessionId: { type: String, required: true },
  static: { type: Array, default: () => [] },
  dynamic: { type: Array, default: () => [] },
  loading: { type: Boolean, default: false },
  error: { type: String, default: '' },
})

const emit = defineEmits(['refine', 'confirm'])

const localStatic = ref([...props.static])
const localDynamic = ref([...props.dynamic])
const feedback = ref('')

watch(() => props.static, (v) => { localStatic.value = [...v] })
watch(() => props.dynamic, (v) => { localDynamic.value = [...v] })

function onRefine() {
  if (!feedback.value.trim()) return
  emit('refine', { feedback: feedback.value.trim() })
  feedback.value = ''
}

function onConfirm() {
  emit('confirm', {
    sessionId: props.sessionId,
    static: localStatic.value.map(s => s.trim()).filter(Boolean),
    dynamic: localDynamic.value.map(s => s.trim()).filter(Boolean),
  })
}
</script>
