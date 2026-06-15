<template>
  <div class="flex flex-col gap-4 p-4 h-full min-h-0">

    <!-- 상단: 압축 업로드 카드 2열 -->
    <div v-if="canManage" class="grid grid-cols-2 gap-4 flex-shrink-0">

      <!-- ① 구역 정보 등록 -->
      <div class="rounded-xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
        <div class="flex items-center justify-between mb-1">
          <h2 class="font-semibold text-base" style="color: var(--text-primary);">구역 정보 등록</h2>
          <button
            class="text-xs px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5 flex-shrink-0"
            style="background: var(--bg-elevated); color: var(--text-muted); border: 1px solid var(--border);"
            @click="downloadSample"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M12 4v12M8 12l4 4 4-4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            샘플 다운로드
          </button>
        </div>
        <p class="text-xs mb-3" style="color: var(--text-subtle);">구역을 먼저 등록하면 매뉴얼 분석 시 구역별 체크리스트가 자동 생성됩니다</p>

        <!-- 파일 선택 버튼 (드래그 포함) -->
        <div class="flex items-center gap-2 mb-3"
          @dragover.prevent="isCsvDragging = true"
          @dragleave.prevent="isCsvDragging = false"
          @drop.prevent="onCsvDrop"
        >
          <button
            class="text-xs px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
            :style="isCsvDragging
              ? 'background: rgba(59,130,246,0.15); color: #93c5fd; border: 1px solid rgba(59,130,246,0.5);'
              : 'background: rgba(59,130,246,0.1); color: #60a5fa; border: 1px solid rgba(59,130,246,0.3);'"
            @click="csvInput.click()"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M12 4v12M8 8l4-4 4 4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            CSV · XLSX 파일 선택
          </button>
          <span class="text-xs" style="color: var(--text-subtle);">최대 5MB · 드래그 가능</span>
          <input ref="csvInput" type="file" class="hidden" accept=".csv,.xlsx" @change="onCsvChange" />
        </div>
        <p v-if="csvError" class="text-xs mb-2" style="color: var(--red);">{{ csvError }}</p>

        <div v-if="zoneFile" class="rounded-lg px-3 py-2 mb-2 flex items-center gap-2"
          style="background: var(--bg-elevated); border: 1px solid var(--border);">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--green); flex-shrink:0;">
            <path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="text-xs truncate flex-1" style="color: var(--text-primary);">{{ zoneFile.name }}</span>
          <button
            class="text-xs py-0.5 px-2.5 rounded-md bg-blue-600 text-white hover:bg-blue-500 transition-colors flex-shrink-0"
            :disabled="zoneRegister.loading"
            @click="onRegisterZones"
          >
            <span v-if="zoneRegister.loading" class="flex items-center gap-1">
              <span class="w-2.5 h-2.5 border-2 border-white border-t-transparent rounded-full animate-spin inline-block"></span>
              등록 중
            </span>
            <span v-else>구역 등록</span>
          </button>
        </div>
        <p v-if="zoneRegister.error" class="text-xs mb-2" style="color: var(--red);">{{ zoneRegister.error }}</p>

        <div v-if="registeredZones.length" class="flex flex-wrap gap-1.5">
          <span
            v-for="z in registeredZones" :key="z"
            class="text-xs px-2.5 py-1 rounded-full font-medium"
            style="background: rgba(59,130,246,0.12); color: #93c5fd; border: 1px solid rgba(59,130,246,0.25);"
          >{{ z }}</span>
        </div>
        <p v-else class="text-xs" style="color: var(--text-subtle);">등록된 구역 없음</p>
      </div>

      <!-- ② 매뉴얼 파일 관리 -->
      <div class="rounded-xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
        <h2 class="font-semibold text-base mb-1" style="color: var(--text-primary);">매뉴얼 파일 관리</h2>
        <p class="text-xs mb-3" style="color: var(--text-subtle);">분석할 PDF 안전 문서를 업로드하세요</p>

        <!-- 파일 선택 버튼 (드래그 포함) -->
        <div class="flex items-center gap-2 mb-3"
          @dragover.prevent="isDragging = true"
          @dragleave.prevent="isDragging = false"
          @drop.prevent="onDrop"
        >
          <button
            class="text-xs px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
            :style="isDragging
              ? 'background: rgba(59,130,246,0.15); color: #93c5fd; border: 1px solid rgba(59,130,246,0.5);'
              : 'background: rgba(59,130,246,0.1); color: #60a5fa; border: 1px solid rgba(59,130,246,0.3);'"
            @click="fileInput.click()"
          >
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M12 4v12M8 8l4-4 4 4" stroke-linecap="round" stroke-linejoin="round"/>
            </svg>
            PDF 파일 선택
          </button>
          <span class="text-xs" style="color: var(--text-subtle);">최대 20MB · 드래그 가능</span>
          <input ref="fileInput" type="file" class="hidden" accept=".pdf" @change="onFileChange" />
        </div>
        <p v-if="uploadError" class="text-xs mb-2" style="color: var(--red);">{{ uploadError }}</p>

        <div v-if="docFile" class="rounded-lg px-3 py-2 flex items-center gap-2"
          style="background: var(--bg-elevated); border: 1px solid var(--border);">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--green); flex-shrink:0;">
            <path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          <span class="text-xs truncate" style="color: var(--text-primary);">{{ docFile.name }}</span>
        </div>
      </div>

    </div>

    <!-- 하단: 스크롤 가능한 분석 카드 2열 -->
    <div v-if="canManage" class="grid grid-cols-2 gap-4 flex-1 min-h-0">

      <!-- ③ 체크리스트 검토 -->
      <div class="rounded-xl flex flex-col min-h-0" style="background: var(--bg-card); border: 1px solid var(--border);">
        <!-- 고정 헤더 + 분석 버튼 -->
        <div class="p-4 flex-shrink-0">
          <h2 class="font-semibold text-base mb-3" style="color: var(--text-primary);">체크리스트 검토</h2>
          <button
            :disabled="!docFile || checklist.loading"
            class="w-full py-2.5 rounded-xl font-semibold text-sm transition-all"
            :class="docFile && !checklist.loading
              ? 'bg-blue-600 text-white hover:bg-blue-500 shadow-lg shadow-blue-900/30'
              : 'text-[#48484a] cursor-not-allowed'"
            :style="!docFile || checklist.loading ? 'background: var(--bg-elevated);' : ''"
            @click="onAnalyze"
          >
            <span v-if="checklist.loading" class="flex items-center justify-center gap-2">
              <span class="w-4 h-4 border-2 border-white border-t-transparent rounded-full animate-spin inline-block"></span>
              분석 중...
            </span>
            <span v-else>{{ docFile ? '분석 시작' : 'PDF를 먼저 업로드하세요' }}</span>
          </button>
        </div>

        <!-- 스크롤 영역 -->
        <div class="flex-1 overflow-y-auto min-h-0 px-4 pb-4">
          <div v-if="checklist.error && !checklist.sessionId" class="rounded-xl p-3 mb-3"
            style="background: var(--bg-elevated); border: 1px solid var(--border);">
            <p class="text-sm" style="color: var(--red);">{{ checklist.error }}</p>
          </div>

          <div v-if="checklist.sessionId">
            <ChecklistReview
              :session-id="checklist.sessionId"
              :static="checklist.static"
              :dynamic="checklist.dynamic"
              :loading="checklist.loading"
              :error="checklist.error"
              @refine="onRefine"
              @confirm="onConfirm"
            />
            <p v-if="checklist.saved" class="text-xs mt-3 text-center" style="color: var(--green);">
              체크리스트가 저장되었습니다.
            </p>
          </div>

          <p v-if="!checklist.sessionId && !checklist.loading && !checklist.error" class="text-sm text-center py-6" style="color: var(--text-subtle);">
            PDF 분석 후 체크리스트가 표시됩니다
          </p>
        </div>
      </div>

      <!-- ④ 구역별 확인 항목 -->
      <div class="rounded-xl flex flex-col min-h-0" style="background: var(--bg-card); border: 1px solid var(--border);">
        <!-- 고정 헤더 -->
        <div class="p-4 pb-3 flex-shrink-0">
          <div class="flex items-center justify-between mb-0.5">
            <h2 class="font-semibold text-base" style="color: var(--text-primary);">구역별 확인 항목</h2>
            <button
              v-if="checklist.zones.length && checklist.sessionId"
              :disabled="checklist.loading"
              class="text-xs px-3 py-1.5 rounded-lg bg-blue-600 text-white hover:bg-blue-500 transition-colors disabled:opacity-50"
              @click="onConfirmZones"
            >
              <span v-if="checklist.loading" class="flex items-center gap-1">
                <span class="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin inline-block"></span>
                저장 중
              </span>
              <span v-else>확정</span>
            </button>
          </div>
          <p v-if="checklist.zones.length" class="text-xs" style="color: var(--text-subtle);">항목에 마우스를 올려 연필 아이콘으로 수정·삭제할 수 있습니다.</p>
          <p v-if="checklist.zoneSaved" class="text-xs mt-1" style="color: var(--green);">구역별 항목이 저장되었습니다.</p>
          <p v-if="checklist.zoneError" class="text-xs mt-1" style="color: var(--red);">{{ checklist.zoneError }}</p>
        </div>

        <!-- 스크롤 영역 -->
        <div class="flex-1 overflow-y-auto min-h-0 px-4 pb-4">
          <div v-if="checklist.zones.length" class="flex flex-col gap-3">
            <div v-for="zone in checklist.zones" :key="zone.zone"
              class="rounded-xl p-3" style="background: var(--bg-elevated); border: 1px solid var(--border);">
              <p class="text-sm font-semibold mb-2.5" style="color: var(--text-primary);">{{ zone.zone }}</p>
              <div class="mb-2.5">
                <span class="text-[10px] font-semibold inline-block mb-1.5" style="color: var(--text-subtle);">정적</span>
                <div class="space-y-1.5">
                  <ChecklistItem
                    v-for="(item, i) in zone.static"
                    :key="'s' + i"
                    :item="item"
                    @update="zone.static[i] = $event"
                    @remove="zone.static.splice(i, 1)"
                  />
                  <button class="text-xs" style="color: var(--blue);" @click="zone.static.push('')">+ 항목 추가</button>
                </div>
              </div>
              <div>
                <span class="text-[10px] font-semibold inline-block mb-1.5" style="color: var(--text-subtle);">동적</span>
                <div class="space-y-1.5">
                  <ChecklistItem
                    v-for="(item, i) in zone.dynamic"
                    :key="'d' + i"
                    :item="item"
                    @update="zone.dynamic[i] = $event"
                    @remove="zone.dynamic.splice(i, 1)"
                  />
                  <button class="text-xs" style="color: var(--blue);" @click="zone.dynamic.push('')">+ 항목 추가</button>
                </div>
              </div>
            </div>
          </div>
          <p v-else class="text-sm text-center py-6" style="color: var(--text-subtle);">분석 후 구역별 항목이 표시됩니다</p>
        </div>
      </div>

    </div>

  </div>
</template>

<script>
export default { name: 'ManualView' }
</script>

<script setup>
import { ref, onMounted, computed } from 'vue'
import { storeToRefs } from 'pinia'
import { useManualStore } from '../stores/manualStore.js'
import { analyzeManual, refineManual, confirmManual, registerZones, fetchZones } from '../api/manuals.js'
import { useAuthStore } from '../stores/authStore.js'
import ChecklistReview from '../components/manual/ChecklistReview.vue'
import ChecklistItem from '../components/manual/ChecklistItem.vue'

const store = useManualStore()
const authStore = useAuthStore()

// storeToRefs: ref 값들을 반응형으로 분리 (탭 이동 후에도 유지됨)
const { docFile, uploadError, zoneFile, csvError, registeredZones } = storeToRefs(store)
// reactive 객체는 직접 참조
const checklist = store.checklist
const zoneRegister = store.zoneRegister

const canManage = computed(() => authStore.user?.role === 'admin')

// 순수 UI 상태만 로컬
const fileInput = ref(null)
const isDragging = ref(false)
const csvInput = ref(null)
const isCsvDragging = ref(false)

async function loadRegisteredZones() {
  try { registeredZones.value = await fetchZones(null) } catch { registeredZones.value = [] }
}

onMounted(() => {
  if (registeredZones.value.length === 0) loadRegisteredZones()
})

// 문서 업로드
const MAX_SIZE = 20 * 1024 * 1024

function validate(file) {
  if (!file.name.match(/\.pdf$/i)) return 'PDF 파일만 업로드할 수 있습니다'
  if (file.size > MAX_SIZE) return '파일 크기는 20MB 이하여야 합니다'
  return null
}

async function handleFile(file) {
  uploadError.value = ''
  const err = validate(file)
  if (err) { uploadError.value = err; return }
  await store.upload(file, null)
  docFile.value = file
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

// 구역 파일 업로드
const CSV_MAX_SIZE = 5 * 1024 * 1024

function validateCsv(file) {
  if (!file.name.match(/\.(csv|xlsx)$/i)) return 'CSV 또는 XLSX 파일만 업로드할 수 있습니다'
  if (file.size > CSV_MAX_SIZE) return '파일 크기는 5MB 이하여야 합니다'
  return null
}

function handleCsvFile(file) {
  csvError.value = ''
  const err = validateCsv(file)
  if (err) { csvError.value = err; return }
  zoneFile.value = file
}

function onCsvChange(e) {
  const file = e.target.files[0]
  if (file) handleCsvFile(file)
  e.target.value = ''
}

function onCsvDrop(e) {
  isCsvDragging.value = false
  const file = e.dataTransfer.files[0]
  if (file) handleCsvFile(file)
}

function downloadSample() {
  const a = document.createElement('a')
  a.href = '/zones_sample.xlsx'
  a.download = 'zones_sample.xlsx'
  a.click()
}

async function onRegisterZones() {
  zoneRegister.loading = true
  zoneRegister.error = ''
  try {
    await registerZones(zoneFile.value, null)
    await loadRegisteredZones()
  } catch (e) {
    const detail = e?.response?.data?.detail
    zoneRegister.error = typeof detail === 'string' ? detail : '등록에 실패했습니다.'
  } finally {
    zoneRegister.loading = false
  }
}

// 분석
async function onAnalyze() {
  checklist.sessionId = ''
  checklist.static = []
  checklist.dynamic = []
  checklist.staticCategories = []
  checklist.dynamicCategories = []
  checklist.zones = []
  checklist.saved = false
  checklist.error = ''
  checklist.loading = true
  try {
    const result = await analyzeManual(docFile.value, null)
    checklist.sessionId = result.session_id
    checklist.static = result.static
    checklist.dynamic = result.dynamic
    checklist.staticCategories = result.static_categories || []
    checklist.dynamicCategories = result.dynamic_categories || []
    checklist.zones = (result.zones || []).map(z => ({
      zone: z.zone,
      static: z.static || [],
      dynamic: z.dynamic || [],
    }))
  } catch (e) {
    const detail = e?.response?.data?.detail
    if (typeof detail === 'string') checklist.error = detail
    else if (Array.isArray(detail)) checklist.error = detail.map(d => d.msg).join(', ')
    else checklist.error = `분석에 실패했습니다. (${e?.response?.status ?? 'network'}) 다시 시도해주세요.`
  } finally {
    checklist.loading = false
  }
}

async function onRefine({ feedback }) {
  checklist.loading = true
  checklist.error = ''
  try {
    const result = await refineManual(checklist.sessionId, feedback, null)
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
    await confirmManual(sessionId, staticItems, dynamicItems, checklist.zones, checklist.staticCategories, checklist.dynamicCategories, null)
    checklist.saved = true
    checklist.zoneSaved = false
    store.zoneViewLoaded = false
    loadRegisteredZones()
  } catch {
    checklist.error = '저장에 실패했습니다. 다시 시도해주세요.'
  } finally {
    checklist.loading = false
  }
}

async function onConfirmZones() {
  checklist.loading = true
  checklist.zoneError = ''
  checklist.zoneSaved = false
  try {
    await confirmManual(checklist.sessionId, checklist.static, checklist.dynamic, checklist.zones, checklist.staticCategories, checklist.dynamicCategories, null)
    checklist.zoneSaved = true
    store.zoneViewLoaded = false
  } catch {
    checklist.zoneError = '저장에 실패했습니다. 다시 시도해주세요.'
  } finally {
    checklist.loading = false
  }
}
</script>
