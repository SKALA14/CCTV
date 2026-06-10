<template>
  <div class="p-4 max-w-3xl mx-auto">

    <!-- superadmin 현장 선택 (읽기 전용) -->
    <div v-if="isSuperadmin" class="mb-6">
      <select
        v-model="selectedSiteId"
        class="w-full max-w-xs px-3 py-2 rounded-xl text-sm"
        style="background: var(--bg-elevated); border: 1px solid var(--border); color: var(--text-primary);"
      >
        <option :value="null">현장을 선택하세요</option>
        <option v-for="s in sites" :key="s.id" :value="s.id">{{ s.name }}</option>
      </select>
    </div>

    <!-- 구역 정보 섹션 -->
    <div v-if="canManage" class="mb-8">
      <div class="mb-2 flex items-center justify-between">
        <div>
          <h2 class="font-semibold text-base" style="color: var(--text-primary);">구역 정보</h2>
          <p class="text-xs mt-0.5" style="color: var(--text-subtle);">구역을 먼저 등록하면 매뉴얼 분석 시 구역별 체크리스트가 자동 생성됩니다</p>
        </div>
        <button
          class="text-xs px-3 py-1.5 rounded-lg transition-colors flex items-center gap-1.5"
          style="background: var(--bg-elevated); color: var(--text-muted); border: 1px solid var(--border);"
          @click="downloadSample"
        >
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M12 4v12M8 12l4 4 4-4" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
          샘플 다운로드
        </button>
      </div>

      <div
        class="rounded-xl border-2 border-dashed transition-colors mb-3 flex flex-col items-center justify-center gap-2 py-8 cursor-pointer"
        :class="isCsvDragging ? 'border-blue-500 bg-blue-500/5' : ''"
        :style="!isCsvDragging ? 'border-color: var(--input-border);' : ''"
        @dragover.prevent="isCsvDragging = true"
        @dragleave.prevent="isCsvDragging = false"
        @drop.prevent="onCsvDrop"
        @click="csvInput.click()"
      >
        <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" style="color: var(--text-subtle);">
          <path d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2M12 4v12M8 8l4-4 4 4" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <p class="text-sm" style="color: var(--text-muted);">CSV · XLSX 파일을 드래그하거나 클릭해서 업로드</p>
        <p class="text-xs" style="color: var(--text-subtle);">최대 5MB</p>
        <input ref="csvInput" type="file" class="hidden" accept=".csv,.xlsx" @change="onCsvChange" />
      </div>
      <p v-if="csvError" class="text-sm mb-2" style="color: var(--red);">{{ csvError }}</p>
      <div v-if="zoneFile" class="rounded-xl px-4 py-3 mb-3 flex items-center gap-3"
        style="background: var(--bg-card); border: 1px solid var(--border);">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--green); flex-shrink:0;">
          <path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span class="text-sm truncate flex-1" style="color: var(--text-primary);">{{ zoneFile.name }}</span>
        <button
          class="text-xs py-1 px-3 rounded-lg bg-blue-600 text-white hover:bg-blue-500 transition-colors"
          :disabled="zoneRegister.loading"
          @click="onRegisterZones"
        >
          <span v-if="zoneRegister.loading" class="flex items-center gap-1.5">
            <span class="w-3 h-3 border-2 border-white border-t-transparent rounded-full animate-spin inline-block"></span>
            등록 중
          </span>
          <span v-else>구역 등록</span>
        </button>
      </div>
      <p v-if="zoneRegister.error" class="text-xs mb-2" style="color: var(--red);">{{ zoneRegister.error }}</p>

      <!-- 등록된 구역 목록 -->
      <div v-if="registeredZones.length" class="flex flex-wrap gap-2 mt-1">
        <span
          v-for="z in registeredZones" :key="z"
          class="text-xs px-2.5 py-1 rounded-full"
          style="background: var(--bg-elevated); color: var(--text-muted); border: 1px solid var(--border);"
        >{{ z }}</span>
      </div>
      <p v-else class="text-xs mt-1" style="color: var(--text-subtle);">등록된 구역 없음</p>
    </div>

    <!-- 매뉴얼 분석 섹션 -->
    <div v-if="canManage" class="mb-8">
      <h2 class="font-semibold text-base mb-4" style="color: var(--text-primary);">메뉴얼 파일 관리</h2>

      <div
        class="rounded-xl border-2 border-dashed transition-colors mb-3 flex flex-col items-center justify-center gap-2 py-10 cursor-pointer"
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
        <p class="text-sm" style="color: var(--text-muted);">안전 문서를 드래그하거나 클릭해서 업로드</p>
        <p class="text-xs" style="color: var(--text-subtle);">PDF · 최대 20MB</p>
        <input ref="fileInput" type="file" class="hidden" accept=".pdf" @change="onFileChange" />
      </div>
      <p v-if="uploadError" class="text-sm mb-3" style="color: var(--red);">{{ uploadError }}</p>
      <div v-if="docFile" class="rounded-xl px-4 py-3 mb-3 flex items-center gap-3"
        style="background: var(--bg-card); border: 1px solid var(--border);">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color: var(--green); flex-shrink:0;">
          <path d="M20 6L9 17l-5-5" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
        <span class="text-sm truncate" style="color: var(--text-primary);">{{ docFile.name }}</span>
      </div>

      <button
        :disabled="!docFile || checklist.loading"
        class="w-full py-3 rounded-xl font-semibold text-sm transition-all mb-6"
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
        <span v-else>{{ docFile ? '분석 시작' : 'PDF를 업로드하세요' }}</span>
      </button>

      <div v-if="checklist.error && !checklist.sessionId" class="rounded-xl p-4 mb-6"
        style="background: var(--bg-card); border: 1px solid var(--border);">
        <p class="text-sm" style="color: var(--red);">{{ checklist.error }}</p>
      </div>

      <div v-if="checklist.sessionId" class="rounded-xl p-4 mb-6"
        style="background: var(--bg-card); border: 1px solid var(--border);">
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

      <div v-if="checklist.zones.length" class="mb-6">
        <h3 class="font-semibold text-sm mb-3" style="color: var(--text-primary);">구역별 확인 항목</h3>
        <div class="flex flex-col gap-3">
          <div v-for="zone in checklist.zones" :key="zone.zone"
            class="rounded-xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
            <p class="text-sm font-semibold mb-2" style="color: var(--text-primary);">{{ zone.zone }}</p>
            <div v-if="zone.static?.length" class="mb-2">
              <p class="text-[11px] font-medium mb-1" style="color: var(--text-subtle);">STATIC</p>
              <ul class="flex flex-col gap-1">
                <li v-for="item in zone.static" :key="item" class="text-xs" style="color: var(--text-muted);">· {{ item }}</li>
              </ul>
            </div>
            <div v-if="zone.dynamic?.length">
              <p class="text-[11px] font-medium mb-1" style="color: var(--text-subtle);">DYNAMIC</p>
              <ul class="flex flex-col gap-1">
                <li v-for="item in zone.dynamic" :key="item" class="text-xs" style="color: var(--text-muted);">· {{ item }}</li>
              </ul>
            </div>
            <p v-if="!zone.static?.length && !zone.dynamic?.length" class="text-xs" style="color: var(--text-subtle);">해당 구역에 적용할 항목 없음</p>
          </div>
        </div>
      </div>
    </div>

    <!-- 파일 목록 -->
    <template v-if="canManage">
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
            @click="store.remove(file.id, manageSiteId)"
          >삭제</button>
        </div>
      </div>
    </template>

    <!-- 확정 체크리스트 (읽기 전용, 모든 역할) -->
    <div class="mb-8">
      <h2 class="font-semibold text-base mb-1" style="color: var(--text-primary);">현재 적용 중인 체크리스트</h2>
      <p class="text-xs mb-3" style="color: var(--text-subtle);">VLM 분석에 실제 사용되는 확정 체크리스트입니다.</p>

      <div v-if="registeredZones.length" class="flex flex-wrap gap-2 mb-4">
        <span v-for="z in registeredZones" :key="z"
          class="text-xs px-2.5 py-1 rounded-full"
          style="background: var(--bg-elevated); color: var(--text-muted); border: 1px solid var(--border);"
        >{{ z }}</span>
      </div>

      <div class="grid grid-cols-1 gap-4">
        <div class="rounded-xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
          <p class="text-[11px] font-medium mb-2" style="color: var(--text-subtle);">STATIC</p>
          <pre v-if="confirmedChecklist.static" class="text-xs whitespace-pre-wrap leading-relaxed" style="color: var(--text-muted);">{{ confirmedChecklist.static }}</pre>
          <p v-else class="text-xs" style="color: var(--text-subtle);">확정된 STATIC 체크리스트 없음</p>
        </div>
        <div class="rounded-xl p-4" style="background: var(--bg-card); border: 1px solid var(--border);">
          <p class="text-[11px] font-medium mb-2" style="color: var(--text-subtle);">DYNAMIC</p>
          <pre v-if="confirmedChecklist.dynamic" class="text-xs whitespace-pre-wrap leading-relaxed" style="color: var(--text-muted);">{{ confirmedChecklist.dynamic }}</pre>
          <p v-else class="text-xs" style="color: var(--text-subtle);">확정된 DYNAMIC 체크리스트 없음</p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, reactive, onMounted, computed, watch } from 'vue'
import { useManualStore } from '../stores/manualStore.js'
import { analyzeManual, refineManual, confirmManual, registerZones, fetchZones, fetchChecklist } from '../api/manuals.js'
import { getSites } from '../api/sites.js'
import { useAuthStore } from '../stores/authStore.js'
import ChecklistReview from '../components/manual/ChecklistReview.vue'

const store = useManualStore()
const authStore = useAuthStore()
const isSuperadmin = computed(() => authStore.isSuperadmin)

const sites = ref([])
const selectedSiteId = ref(null)
const confirmedChecklist = reactive({ static: '', dynamic: '' })

const registeredZones = ref([])

// 관리 권한: admin은 항상(자기 현장), superadmin은 현장을 선택했을 때. viewer는 읽기 전용.
const canManage = computed(() => {
  if (authStore.user?.role === 'admin') return true
  if (isSuperadmin.value && selectedSiteId.value) return true
  return false
})

// 쓰기 API에 전달할 현장 — admin은 null(백엔드가 자기 현장), superadmin은 선택 현장
const manageSiteId = computed(() => (isSuperadmin.value ? selectedSiteId.value : null))

async function loadConfirmedView() {
  const sid = isSuperadmin.value ? selectedSiteId.value : null
  if (isSuperadmin.value && !sid) {
    confirmedChecklist.static = ''
    confirmedChecklist.dynamic = ''
    registeredZones.value = []
    return
  }
  try {
    const cl = await fetchChecklist(sid)
    confirmedChecklist.static = cl.static || ''
    confirmedChecklist.dynamic = cl.dynamic || ''
  } catch { confirmedChecklist.static = ''; confirmedChecklist.dynamic = '' }
  try { registeredZones.value = await fetchZones(sid) } catch { registeredZones.value = [] }
  // 관리 가능하면 해당 현장의 업로드 파일 목록도 로드
  if (canManage.value) store.load(sid)
}

watch(selectedSiteId, loadConfirmedView)

onMounted(async () => {
  if (isSuperadmin.value) {
    try { sites.value = await getSites() } catch (e) { console.warn('현장 로드 실패:', e?.message ?? e) }
  }
  loadConfirmedView()
})

// 문서 업로드
const fileInput = ref(null)
const isDragging = ref(false)
const uploadError = ref('')
const docFile = ref(null)

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
  await store.upload(file, manageSiteId.value)
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
const csvInput = ref(null)
const isCsvDragging = ref(false)
const csvError = ref('')
const zoneFile = ref(null)
const zoneRegister = reactive({ loading: false, error: '' })

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
    await registerZones(zoneFile.value, manageSiteId.value)
    await loadConfirmedView()
  } catch (e) {
    const detail = e?.response?.data?.detail
    zoneRegister.error = typeof detail === 'string' ? detail : '등록에 실패했습니다.'
  } finally {
    zoneRegister.loading = false
  }
}

// 분석
const checklist = reactive({
  sessionId: '',
  static: [],
  dynamic: [],
  staticCategories: [],
  dynamicCategories: [],
  zones: [],
  loading: false,
  error: '',
  saved: false,
})

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
    const result = await analyzeManual(docFile.value, manageSiteId.value)
    checklist.sessionId = result.session_id
    checklist.static = result.static
    checklist.dynamic = result.dynamic
    checklist.staticCategories = result.static_categories || []
    checklist.dynamicCategories = result.dynamic_categories || []
    checklist.zones = result.zones || []
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
    const result = await refineManual(checklist.sessionId, feedback, manageSiteId.value)
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
<<<<<<< HEAD
    await confirmManual(sessionId, staticItems, dynamicItems, checklist.zones, checklist.staticCategories, checklist.dynamicCategories)
=======
    await confirmManual(sessionId, staticItems, dynamicItems, checklist.zones, checklist.staticCategories, checklist.dynamicCategories, manageSiteId.value)
>>>>>>> dev1-woos
    checklist.saved = true
    loadConfirmedView()
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
