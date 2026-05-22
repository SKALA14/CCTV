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

        <!-- 추가 탐지 항목 -->
        <div>
          <label class="block text-xs mb-1.5" style="color: var(--text-muted);">추가 탐지 항목 설명</label>
          <div class="flex gap-2">
            <textarea
              v-model="instructionText"
              placeholder="이 채널에서 추가로 탐지할 항목을 자유롭게 입력하세요 (예: '지게차 주차구역 이탈 모니터링')"
              rows="2"
              class="flex-1 px-3 py-2.5 rounded-lg text-sm focus:outline-none resize-none"
              style="background: var(--input-bg); border: 1px solid var(--input-border); color: var(--text-primary);"
              :disabled="instruction.loading"
            />
            <button
              class="px-3 py-2 rounded-lg text-sm self-end transition-colors"
              style="background: var(--bg-elevated); color: var(--text-primary); border: 1px solid var(--border);"
              :disabled="instruction.loading || !instructionText.trim()"
              @click="analyzeInstructionText"
            >분석</button>
          </div>
          <p v-if="instruction.error" class="text-xs mt-1" style="color: var(--red);">{{ instruction.error }}</p>
          <p v-if="instruction.confirmed" class="text-xs mt-1" style="color: var(--green, #16a34a);">추가 항목이 저장되었습니다.</p>
        </div>

        <!-- 채널별 체크리스트 미니 리뷰 -->
        <div
          v-if="instruction.static.length || instruction.dynamic.length"
          class="rounded-lg p-3"
          style="background: var(--bg-elevated); border: 1px solid var(--border);"
        >
          <ChecklistReview
            :session-id="instruction.sessionId"
            :static="instruction.static"
            :dynamic="instruction.dynamic"
            :loading="instruction.loading"
            :error="instruction.error"
            @refine="() => {}"
            @confirm="onInstructionConfirm"
          />
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
import { ref, reactive } from 'vue'
import { detectSourceType } from '../../utils/detectSourceType.js'
import { analyzeInstruction, confirmInstruction } from '../../api/manuals.js'
import ChecklistReview from '../manual/ChecklistReview.vue'

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
  description: props.initial?.description || '',
})

const errors = reactive({ name: '', rtspUrl: '' })

const instructionText = ref('')
const instruction = reactive({
  sessionId: '',
  static: [],
  dynamic: [],
  loading: false,
  error: '',
  confirmed: false,
})

function validate() {
  errors.name    = ''
  errors.rtspUrl = ''

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

  if (form.sourceType === 'url' && !form.rtspUrl.trim()) {
    errors.rtspUrl = 'URL을 입력해주세요.'
    return false
  }

  return true
}

async function analyzeInstructionText() {
  if (!instructionText.value.trim()) return
  const cameraId = `cam${props.slotIndex}`
  instruction.sessionId = ''
  instruction.static = []
  instruction.dynamic = []
  instruction.confirmed = false
  instruction.error = ''
  instruction.loading = true
  try {
    const result = await analyzeInstruction(cameraId, instructionText.value)
    instruction.sessionId = cameraId
    instruction.static = result.static
    instruction.dynamic = result.dynamic
  } catch {
    instruction.error = '분석에 실패했습니다. 다시 시도해주세요.'
  } finally {
    instruction.loading = false
  }
}

async function onInstructionConfirm({ static: s, dynamic: d }) {
  const cameraId = `cam${props.slotIndex}`
  instruction.loading = true
  try {
    await confirmInstruction(cameraId, s, d)
    instruction.confirmed = true
    instruction.static = s
    instruction.dynamic = d
  } catch {
    instruction.error = '저장에 실패했습니다.'
  } finally {
    instruction.loading = false
  }
}

function submit() {
  if (!validate()) return

  const isWebcam = form.sourceType === 'webcam'
  const trimmedUrl = form.rtspUrl.trim()

  emit('submit', {
    slot:        props.slotIndex,
    name:        form.name.trim(),
    url:         isWebcam ? 'webcam' : trimmedUrl,
    rtspUrl:     isWebcam ? null : trimmedUrl,
    channelName: `cam${props.slotIndex}`,
    sourceType:  isWebcam ? 'webcam' : detectSourceType(trimmedUrl),
    description: form.description,
  })
}
</script>
