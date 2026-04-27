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
          v-if="file.type === 'application/pdf'"
          class="text-xs rounded px-2 py-1 transition-colors mr-1"
          style="color: var(--text-muted); border: 1px solid var(--border);"
          @click="openFile(file)"
        >열기</button>
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
import { ref, onMounted } from 'vue'
import { useManualStore } from '../stores/manualStore.js'

const store = useManualStore()
const fileInput = ref(null)
const isDragging = ref(false)
const uploadError = ref('')

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

function openFile(file) {
  window.open(URL.createObjectURL(file), '_blank')
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
