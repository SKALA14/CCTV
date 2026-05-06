<template>
  <div
    class="fixed inset-0 z-50 flex items-center justify-center bg-black/60 backdrop-blur-sm"
    @click.self="$emit('close')"
  >
    <div
      class="w-[480px] rounded-2xl p-6 shadow-2xl"
      style="background: var(--bg-card); border: 1px solid var(--border);"
    >
      <h3 class="font-semibold text-base mb-1" style="color: var(--text-primary);">
        {{ isEdit ? '채널 수정' : `슬롯 ${props.slotIndex}에 채널 등록` }}
      </h3>
      <p class="text-xs mb-5" style="color: var(--text-muted);">
        camera_id: cam{{ props.slotIndex }}
      </p>

      <div class="space-y-4">
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted);">채널명 *</label>
          <input
            v-model="form.name"
            type="text"
            placeholder="예: 정문 CCTV"
            class="w-full h-10 px-3 rounded-lg text-sm focus:outline-none transition-colors"
            :style="`background: var(--input-bg); border: 1px solid ${errors.name ? '#ef4444' : 'var(--input-border)'}; color: var(--text-primary);`"
          />
          <p v-if="errors.name" class="text-xs mt-1 text-red-400">{{ errors.name }}</p>
        </div>

        <div>
          <label class="block text-xs mb-2" style="color: var(--text-muted);">소스 타입</label>
          <div class="flex gap-2 mb-3">
            <button
              class="px-3 py-1.5 rounded-lg text-sm transition-colors"
              :class="form.sourceType === 'url' ? 'bg-blue-600 text-white' : ''"
              :style="form.sourceType !== 'url' ? 'border: 1px solid var(--input-border); color: var(--text-muted);' : ''"
              @click="form.sourceType = 'url'"
            >소스 URL</button>
            <button
              class="px-3 py-1.5 rounded-lg text-sm transition-colors"
              :class="form.sourceType === 'webcam' ? 'bg-blue-600 text-white' : ''"
              :style="form.sourceType !== 'webcam' ? 'border: 1px solid var(--input-border); color: var(--text-muted);' : ''"
              @click="form.sourceType = 'webcam'"
            >웹캠</button>
          </div>
          <div v-if="form.sourceType === 'url'" class="space-y-2">
            <input
              v-model="form.rtspUrl"
              type="text"
              placeholder="rtsp://192.168.x.x:554/stream 또는 http://..."
              class="w-full h-10 px-3 rounded-lg text-sm font-mono focus:outline-none transition-colors"
              :style="`background: var(--input-bg); border: 1px solid ${errors.rtspUrl ? '#ef4444' : 'var(--input-border)'}; color: var(--text-primary);`"
            />
            <p v-if="errors.rtspUrl" class="text-xs mt-1 text-red-400">{{ errors.rtspUrl }}</p>
            <input
              v-model="form.channelName"
              type="text"
              placeholder="mediamtx 스트림 경로 (예: cam0)"
              class="w-full h-10 px-3 rounded-lg text-sm font-mono focus:outline-none transition-colors"
              :style="`background: var(--input-bg); border: 1px solid ${errors.channelName ? '#ef4444' : 'var(--input-border)'}; color: var(--text-primary);`"
            />
            <p v-if="errors.channelName" class="text-xs mt-1 text-red-400">{{ errors.channelName }}</p>
            <p class="text-xs" style="color: var(--text-muted);">
              rtsp://는 mediamtx WebRTC 경유 재생
            </p>
          </div>
          <p
            v-if="form.sourceType === 'webcam'"
            class="text-xs px-3 py-2 rounded-lg"
            style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-muted);"
          >브라우저 웹캠을 사용합니다 (저장 후 권한 요청)</p>
        </div>

        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted);">상세 설명</label>
          <textarea
            v-model="form.description"
            placeholder="채널 위치, 용도 등 메모"
            rows="2"
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

const props = defineProps({
  slotIndex: { type: Number, default: 0 },
  initial: Object,
  existingNames: { type: Array, default: () => [] },
})
const emit = defineEmits(['close', 'submit'])

const isEdit = !!props.initial?.name

const form = reactive({
  name:        props.initial?.name        || '',
  sourceType:  props.initial?.url === 'webcam' ? 'webcam' : 'url',
  rtspUrl:     props.initial?.rtspUrl     || '',
  channelName: props.initial?.channelName || `cam${props.slotIndex}`,
  description: props.initial?.description || '',
  options:     props.initial?.options     || [],
})

const errors = reactive({ name: '', rtspUrl: '', channelName: '' })

function validate() {
  errors.name        = ''
  errors.rtspUrl     = ''
  errors.channelName = ''

  const trimmed = form.name.trim()
  if (!trimmed) {
    errors.name = '채널명을 입력해주세요.'
    return false
  }
  const duplicate = props.existingNames
    .map(n => n.trim().toLowerCase())
    .includes(trimmed.toLowerCase())
  if (duplicate) {
    errors.name = '이미 사용 중인 채널명입니다.'
    return false
  }

  if (form.sourceType === 'url') {
    if (!form.rtspUrl.trim()) {
      errors.rtspUrl = 'URL을 입력해주세요.'
      return false
    }
    if (!form.channelName.trim()) {
      errors.channelName = '스트림 경로를 입력해주세요.'
      return false
    }
  }

  return true
}

function toggleOption(opt) {
  const idx = form.options.indexOf(opt)
  idx === -1 ? form.options.push(opt) : form.options.splice(idx, 1)
}

function submit() {
  if (!validate()) return

  const isWebcam = form.sourceType === 'webcam'

  emit('submit', {
    slot:        props.slotIndex,
    name:        form.name.trim(),
    url:         isWebcam ? 'webcam' : form.rtspUrl.trim(),
    rtspUrl:     isWebcam ? null : form.rtspUrl.trim(),
    channelName: isWebcam ? null : form.channelName.trim(),
    description: form.description,
    options:     form.options,
  })
}
</script>
