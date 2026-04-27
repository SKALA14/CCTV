<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    @click.self="$emit('close')"
  >
    <div
      class="w-[480px] rounded-2xl p-6 shadow-2xl"
      style="background: var(--bg-card); border: 1px solid var(--border);"
    >
      <h3 class="font-semibold text-base mb-5" style="color: var(--text-primary);">
        {{ isEdit ? '채널 수정' : '채널 추가' }}
      </h3>

      <div class="space-y-4">
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted);">채널명 *</label>
          <input
            v-model="form.name"
            type="text"
            placeholder="예: 정문 CCTV"
            class="w-full h-10 px-3 rounded-lg text-sm focus:outline-none focus:border-blue-500 transition-colors"
            style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-primary);"
          />
        </div>

        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted);">영상 URL *</label>
          <input
            v-model="form.url"
            type="text"
            placeholder="rtsp://192.168.1.1:554/stream"
            class="w-full h-10 px-3 rounded-lg text-sm font-mono focus:outline-none focus:border-blue-500 transition-colors"
            style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-primary);"
          />
        </div>

        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted);">상세 설명</label>
          <textarea
            v-model="form.description"
            placeholder="채널 위치, 용도 등 메모"
            rows="3"
            class="w-full px-3 py-2.5 rounded-lg text-sm focus:outline-none focus:border-blue-500 transition-colors resize-none"
            style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-primary);"
          ></textarea>
        </div>

        <div>
          <label class="block text-xs mb-2" style="color: var(--text-muted);">General 옵션 (복수 선택)</label>
          <div class="flex flex-wrap gap-2">
            <span
              v-for="opt in GENERAL_OPTIONS"
              :key="opt"
              class="px-3 py-1 rounded-full text-sm cursor-pointer transition-colors select-none"
              :class="form.options.includes(opt) ? 'bg-blue-600 text-white' : ''"
              :style="!form.options.includes(opt)
                ? 'border: 1px solid var(--input-border); color: var(--text-muted);'
                : 'border: 1px solid transparent;'"
              @click="toggleOption(opt)"
            >{{ opt }}</span>
          </div>
        </div>
      </div>

      <div class="flex justify-end gap-2 mt-6 pt-5" style="border-top: 1px solid var(--border);">
        <button
          class="px-4 py-2 rounded-lg text-sm transition-colors"
          style="background: var(--bg-elevated); color: var(--text-primary); border: 1px solid var(--border);"
          @click="$emit('close')"
        >취소</button>
        <button
          class="px-4 py-2 rounded-lg bg-blue-600 text-white text-sm hover:bg-blue-500 transition-colors"
          @click="submit"
        >저장</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { reactive } from 'vue'
import { GENERAL_OPTIONS } from '../../constants/events.js'

const props = defineProps({ initial: Object })
const emit = defineEmits(['close', 'submit'])

const isEdit = !!props.initial?.id

const form = reactive({
  name:        props.initial?.name        || '',
  url:         props.initial?.url         || '',
  description: props.initial?.description || '',
  options:     props.initial?.options     || ['쓰러짐 / 추락', '화재 / 연기'],
})

function toggleOption(opt) {
  const idx = form.options.indexOf(opt)
  idx === -1 ? form.options.push(opt) : form.options.splice(idx, 1)
}

function submit() {
  if (!form.name || !form.url) return
  emit('submit', { ...form, id: props.initial?.id })
}
</script>
