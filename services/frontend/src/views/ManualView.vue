<template>
  <div class="p-4 max-w-3xl mx-auto">
    <h2 class="font-semibold text-base mb-4" style="color: var(--text-primary);">메뉴얼 파일 관리</h2>

    <!-- 업로드 존 -->
    <div
      class="rounded-xl border-2 border-dashed transition-colors mb-6 flex flex-col items-center justify-center gap-2 py-10 cursor-pointer"
      :class="isDragging ? 'border-blue-500 bg-blue-500/5' : ''"
      :style="!isDragging ? 'border-color: var(--input-border);' : ''"
      @dragover.prevent="isDragging = true"
      @dragleave.prevent="isDragging = false"
      @drop.prevent="onDrop"
      @click="fileInput.click()"
    >
      <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--text-subtle);">
        <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M12 4v12M8 8l4-4 4 4" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
      <p class="text-sm" style="color: var(--text-muted);">파일을 드래그하거나 클릭해서 업로드</p>
      <p class="text-xs" style="color: var(--text-subtle);">PDF · DOCX · PPTX · XLSX · TXT · 최대 20MB</p>
      <input
        ref="fileInput"
        type="file"
        class="hidden"
        accept=".pdf,.docx,.pptx,.xlsx,.txt"
        @change="onFileChange"
      />
    </div>

    <!-- 에러 -->
    <p v-if="uploadError" class="text-sm mb-4" style="color: var(--red);">{{ uploadError }}</p>

    <!-- PDF 분석 중 로딩 (sessionId 없는 초기 상태) -->
    <div
      v-if="checklist.loading && !checklist.sessionId"
      class="rounded-xl p-6 mb-6 flex flex-col items-center gap-3"
      style="background: var(--bg-card); border: 1px solid var(--border);"
    >
      <div class="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
      <p class="text-sm" style="color: var(--text-muted);">PDF에서 안전 체크리스트를 분석하는 중입니다 (30~60초 소요)...</p>
    </div>

    <!-- PDF 분석 실패 (sessionId 없이 에러만 있는 경우) -->
    <div
      v-if="checklist.error && !checklist.sessionId"
      class="rounded-xl p-4 mb-6"
      style="background: var(--bg-card); border: 1px solid var(--border);"
    >
      <p class="text-sm" style="color: var(--red);">{{ checklist.error }}</p>
    </div>

    <!-- 체크리스트 리뷰 (PDF 분석 후 표시) -->
    <div
      v-if="checklist.sessionId"
      class="rounded-xl p-4 mb-6"
      style="background: var(--bg-card); border: 1px solid var(--border);"
    >
      <ChecklistReview
        :session-id="checklist.sessionId"
        :static="checklist.static"
        :dynamic="checklist.dynamic"
        :loading="checklist.loading"
        :error="checklist.error"
        @refine="onRefine"
        @confirm="onConfirm"
      />
      <p v-if="checklist.saved" class="text-xs mt-3 text-center" style="color: var(--green, #16a34a);">
        체크리스트가 저장되었습니다.
      </p>
    </div>

    <!-- 파일 목록 -->
    <div v-if="store.loading" class="flex justify-center py-8">
      <div class="w-6 h-6 border-2 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
    <div v-else-if="store.files.length === 0" class="text-center py-12 text-sm" style="color: var(--text-subtle);">
      업로드된 메뉴얼이 없습니다
    </div>
    <div v-else class="rounded-xl" style="background: var(--bg-card); border: 1px solid var(--border);">
      <div
        v-for="(file, i) in store.files"
        :key="file.id"
        class="flex items-center gap-3 px-4 py-3"
        :style="i < store.files.length - 1 ? 'border-bottom: 1px solid var(--border);' : ''"
      >
        <div class="w-8 h-8 rounded flex items-center justify-center flex-shrink-0"
          style="background: var(--bg-elevated);">
          <span class="text-[10px] font-mono uppercase" style="color: var(--text-muted);">{{ ext(file.name) }}</span>
        </div>
        <div class="flex-1 min-w-0">
          <p class="text-sm truncate" style="color: var(--text-primary);">{{ file.name }}</p>
          <p class="text-xs" style="color: var(--text-subtle);">{{ formatSize(file.size) }} · {{ formatDate(file.uploaded_at) }}</p>
        </div>
        <button
          class="text-xs rounded px-2 py-1 transition-colors"
          style="color: var(--red); border: 1px solid var(--border);"
          @click="store.remove(file.id)"
        >삭제</button>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted } from 'vue'
import { useManualStore } from '../stores/manualStore.js'
import { analyzeManual, refineManual, confirmManual } from '../api/manuals.js'
import ChecklistReview from '../components/manual/ChecklistReview.vue'

const store = useManualStore()
const fileInput = ref(null)
const isDragging = ref(false)
const uploadError = ref('')

const checklist = reactive({
  sessionId: '',
  static: [],
  dynamic: [],
  loading: false,
  error: '',
  saved: false,
})

const ALLOWED_TYPES = new Set([
  'application/pdf',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation',
  'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
  'text/plain',
])
const MAX_SIZE = 20 * 1024 * 1024

onMounted(() => { store.load() })

function validate(file) {
  if (!ALLOWED_TYPES.has(file.type) && !file.name.match(/\.(pdf|docx|pptx|xlsx|txt)$/i)) {
    return '지원하지 않는 파일 형식입니다 (PDF·DOCX·PPTX·XLSX·TXT만 허용)'
  }
  if (file.size > MAX_SIZE) return '파일 크기는 20MB 이하여야 합니다'
  return null
}

async function handleFile(file) {
  uploadError.value = ''
  const err = validate(file)
  if (err) { uploadError.value = err; return }

  await store.upload(file)

  if (file.name.toLowerCase().endsWith('.pdf')) {
    checklist.sessionId = ''
    checklist.static = []
    checklist.dynamic = []
    checklist.saved = false
    checklist.error = ''
    checklist.loading = true
    try {
      const result = await analyzeManual(file)
      checklist.sessionId = result.session_id
      checklist.static = result.static
      checklist.dynamic = result.dynamic
    } catch {
      checklist.error = '체크리스트 분석에 실패했습니다. 다시 시도해주세요.'
    } finally {
      checklist.loading = false
    }
  }
}

function onFileChange(e) {
  const file = e.target.files[0]
  if (file) handleFile(file)
  e.target.value = ''
}

function onDrop(e) {
  isDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) handleFile(file)
}

async function onRefine({ feedback }) {
  checklist.loading = true
  checklist.error = ''
  try {
    const result = await refineManual(checklist.sessionId, feedback)
    checklist.static = result.static
    checklist.dynamic = result.dynamic
  } catch {
    checklist.error = '재생성에 실패했습니다. 이전 결과를 유지합니다.'
  } finally {
    checklist.loading = false
  }
}

async function onConfirm({ sessionId, static: staticItems, dynamic: dynamicItems }) {
  checklist.loading = true
  checklist.error = ''
  try {
    await confirmManual(sessionId, staticItems, dynamicItems)
    checklist.saved = true
  } catch {
    checklist.error = '저장에 실패했습니다. 다시 시도해주세요.'
  } finally {
    checklist.loading = false
  }
}

function ext(name) { return name.split('.').pop() }

function formatSize(bytes) {
  if (bytes < 1024) return bytes + ' B'
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function formatDate(iso) {
  return new Date(iso).toLocaleString('ko-KR', {
    year: 'numeric', month: '2-digit', day: '2-digit',
    hour: '2-digit', minute: '2-digit',
  })
}
</script>
