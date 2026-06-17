<template>
  <div class="app-shell" :class="{ dark: isDark }">
    <!-- Top Navigation -->
    <header class="topnav">
      <div class="topnav-inner">
        <div class="topnav-actions topnav-actions-only">
          <button class="theme-toggle" @click="toggleTheme" :title="isDark ? '라이트 모드' : '다크 모드'">
            <i :class="isDark ? 'ri-sun-line' : 'ri-moon-line'"></i>
          </button>
          <router-link to="/profile" class="profile-nav-btn">
            <i class="ri-user-3-line"></i>
          </router-link>
        </div>
      </div>
    </header>

    <!-- Main Content -->
    <main class="main-content">
      <!-- Page Header -->
      <div class="page-header">
        <div class="page-header-icon">
          <i class="ri-book-open-line"></i>
        </div>
        <div>
          <h1 class="page-title">Safety Manual</h1>
          <p class="page-desc">구역 등록, PDF 분석, 체크리스트 검토를 한 곳에서 관리할 수 있습니다.</p>
        </div>
      </div>

      <!-- Top Row: 2 Cards -->
      <div class="card-row">
        <!-- ① Zone Registration -->
        <div class="card card-glow">
          <div class="card-header-row">
            <h2 class="card-title">구역 등록</h2>
            <button class="btn-ghost" @click="downloadSample">
              <i class="ri-download-line"></i> 샘플 다운로드
            </button>
          </div>
          <p class="card-hint">구역을 먼저 등록하면 매뉴얼 분석 시 구역별 체크리스트가 자동 생성됩니다</p>

          <div
            class="dropzone"
            :class="{ 'dropzone-active': isCsvDragging }"
            @dragover.prevent="isCsvDragging = true"
            @dragleave.prevent="isCsvDragging = false"
            @drop.prevent="onCsvDrop"
          >
            <button class="btn-accent-soft" @click="$refs.csvInput.click()">
              <i class="ri-upload-line"></i> CSV · XLSX 파일 선택
            </button>
            <span class="dropzone-hint">최대 5MB · 드래그&드롭</span>
            <input ref="csvInput" type="file" class="hidden-input" accept=".csv,.xlsx" @change="onCsvChange" />
          </div>

          <p v-if="csvError" class="error-text">{{ csvError }}</p>
          <p v-if="zoneRegister.error" class="error-text">{{ zoneRegister.error }}</p>

          <div v-if="zoneFile" class="file-chip">
            <i class="ri-check-line check-icon"></i>
            <span class="file-chip-name">{{ zoneFile.name }}</span>
            <button class="btn-accent" :disabled="zoneRegister.loading" @click="onRegisterZones">
              <span v-if="zoneRegister.loading" class="spinner-text">
                <span class="spinner spinner-light"></span> 등록 중
              </span>
              <span v-else>구역 등록</span>
            </button>
          </div>

          <div v-if="registeredZones.length" class="zone-tags">
            <span v-for="z in registeredZones" :key="z" class="zone-tag">{{ z }}</span>
          </div>
          <p v-else class="empty-hint">등록된 구역이 없습니다</p>
        </div>

        <!-- ② Manual File Management -->
        <div class="card card-glow">
          <h2 class="card-title mb">매뉴얼 파일 관리</h2>
          <p class="card-hint">분석할 PDF 안전 문서를 업로드하세요. 여러 파일을 선택하면 합산 분석됩니다.</p>

          <div
            class="dropzone"
            :class="{ 'dropzone-active': isDragging }"
            @dragover.prevent="isDragging = true"
            @dragleave.prevent="isDragging = false"
            @drop.prevent="onDrop"
          >
            <button class="btn-accent-soft" @click="$refs.fileInput.click()">
              <i class="ri-upload-line"></i> PDF 파일 선택
            </button>
            <span class="dropzone-hint">최대 20MB · 다중 선택 · 드래그&드롭</span>
            <input ref="fileInput" type="file" class="hidden-input" accept=".pdf" multiple @change="onFileChange" />
          </div>

          <p v-if="uploadError" class="error-text">{{ uploadError }}</p>

          <div v-if="docFiles.length" class="file-list">
            <div v-for="(f, i) in docFiles" :key="i" class="file-item">
              <i class="ri-file-pdf-line pdf-icon"></i>
              <span class="file-name">{{ f.name }}</span>
              <span class="file-size">{{ formatSize(f.size) }}</span>
              <button class="btn-remove" @click="docFiles.splice(i, 1)"><i class="ri-close-line"></i></button>
            </div>
          </div>
          <div v-else class="empty-drop">
            <i class="ri-file-pdf-line empty-drop-icon"></i>
            <p>PDF 파일을 드래그하거나 선택하세요</p>
          </div>
        </div>
      </div>

      <!-- Bottom Row: 2 Cards -->
      <div class="card-row card-row-bottom">
        <!-- ③ Checklist Review -->
        <div class="card card-glow card-scroll">
          <div class="card-sticky-header">
            <div class="card-header-row">
              <h2 class="card-title">체크리스트 검토</h2>
            </div>

            <button
              v-if="!checklist.sessionId"
              class="btn-analyze"
              :class="{ 'btn-analyze-ready': docFiles.length && !checklist.loading }"
              :disabled="!docFiles.length || checklist.loading"
              @click="onAnalyze"
            >
              <span v-if="checklist.loading" class="spinner-text">
                <span class="spinner spinner-light"></span> 분석 중...
              </span>
              <span v-else>{{ docFiles.length ? `분석 시작 (${docFiles.length}개 파일)` : 'PDF를 먼저 업로드하세요' }}</span>
            </button>
          </div>

          <div class="card-scroll-body">
            <div v-if="checklist.error && !checklist.sessionId" class="error-box">
              <p>{{ checklist.error }}</p>
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
              <p v-if="checklist.saved" class="success-hint mt-2 text-center">
                <i class="ri-check-double-line"></i> 체크리스트가 저장되었습니다.
              </p>
            </div>

            <div v-else-if="!checklist.loading" class="empty-center">
              <i class="ri-clipboard-line empty-center-icon"></i>
              <p>PDF 분석 후 체크리스트가 표시됩니다</p>
            </div>
          </div>
        </div>

        <!-- ④ Zone Checklist -->
        <div class="card card-glow card-scroll">
          <div class="card-sticky-header">
            <div class="card-header-row">
              <h2 class="card-title">구역 체크리스트</h2>
              <button v-if="checklist.zones.length && checklist.sessionId" class="btn-accent" :disabled="checklist.loading" @click="onConfirmZones">
                <span v-if="checklist.loading" class="spinner-text">
                  <span class="spinner spinner-light"></span> 저장 중
                </span>
                <span v-else>확정</span>
              </button>
            </div>
            <p v-if="checklist.zones.length" class="card-hint">항목을 클릭하여 수정·삭제하세요. 왼쪽에서 드래그하여 추가하세요.</p>
            <p v-if="checklist.zoneSaved" class="success-hint"><i class="ri-check-line"></i> 구역 항목이 저장되었습니다.</p>
            <p v-if="checklist.zoneError" class="error-text">{{ checklist.zoneError }}</p>
          </div>

          <div class="card-scroll-body">
            <div v-if="checklist.zones.length" class="zone-list">
              <div v-for="zone in checklist.zones" :key="zone.zone" class="zone-card">
                <div class="zone-card-header">
                  <div class="zone-icon-box">
                    <i class="ri-map-pin-line"></i>
                  </div>
                  <p class="zone-name">{{ zone.zone }}</p>
                </div>

                <!-- Static -->
                <div class="zone-section">
                  <span class="checklist-label">정적</span>
                  <div
                    class="zone-items"
                    :class="{ 'drop-target-active': dropTarget === zone.zone + '-static' }"
                    @dragover.prevent="dropTarget = zone.zone + '-static'"
                    @dragleave.prevent="dropTarget = null"
                    @drop.prevent="onDropToZone($event, zone, 'static')"
                  >
                    <div v-for="(item, i) in zone.static" :key="'zs'+i" class="zone-item-row">
                      <div v-if="editingZone === zone.zone && editingType === 'static' && editingIndex === i" class="edit-inline">
                        <input
                          v-model="editText"
                          class="edit-input"
                          @keydown.enter="saveEdit"
                          @keydown.escape="cancelEdit"
                          ref="editInput"
                        />
                        <button class="btn-icon-done" @click="saveEdit"><i class="ri-check-line"></i></button>
                        <button class="btn-icon-cancel" @click="cancelEdit"><i class="ri-close-line"></i></button>
                      </div>
                      <div v-else class="zone-item-display">
                        <span class="zone-item-text" @click="startEdit(zone.zone, 'static', i, item)">
                          {{ item || '항목 입력...' }}
                        </span>
                        <button class="btn-delete-hover" @click="removeItem(zone.zone, 'static', i)"><i class="ri-delete-bin-line"></i></button>
                      </div>
                    </div>
                    <p v-if="dropTarget === zone.zone + '-static' && !zone.static.length" class="drop-hint">여기에 드롭</p>
                    <button class="btn-add-item" @click="addItem(zone.zone, 'static')"><i class="ri-add-line"></i> 항목 추가</button>
                  </div>
                </div>

                <!-- Dynamic -->
                <div class="zone-section">
                  <span class="checklist-label">동적</span>
                  <div
                    class="zone-items"
                    :class="{ 'drop-target-active': dropTarget === zone.zone + '-dynamic' }"
                    @dragover.prevent="dropTarget = zone.zone + '-dynamic'"
                    @dragleave.prevent="dropTarget = null"
                    @drop.prevent="onDropToZone($event, zone, 'dynamic')"
                  >
                    <div v-for="(item, i) in zone.dynamic" :key="'zd'+i" class="zone-item-row">
                      <div v-if="editingZone === zone.zone && editingType === 'dynamic' && editingIndex === i" class="edit-inline">
                        <input
                          v-model="editText"
                          class="edit-input"
                          @keydown.enter="saveEdit"
                          @keydown.escape="cancelEdit"
                        />
                        <button class="btn-icon-done" @click="saveEdit"><i class="ri-check-line"></i></button>
                        <button class="btn-icon-cancel" @click="cancelEdit"><i class="ri-close-line"></i></button>
                      </div>
                      <div v-else class="zone-item-display">
                        <span class="zone-item-text" @click="startEdit(zone.zone, 'dynamic', i, item)">
                          {{ item || '항목 입력...' }}
                        </span>
                        <button class="btn-delete-hover" @click="removeItem(zone.zone, 'dynamic', i)"><i class="ri-delete-bin-line"></i></button>
                      </div>
                    </div>
                    <p v-if="dropTarget === zone.zone + '-dynamic' && !zone.dynamic.length" class="drop-hint">여기에 드롭</p>
                    <button class="btn-add-item" @click="addItem(zone.zone, 'dynamic')"><i class="ri-add-line"></i> 항목 추가</button>
                  </div>
                </div>
              </div>
            </div>
            <div v-else class="empty-center">
              <i class="ri-building-line empty-center-icon"></i>
              <p>분석 후 구역 항목이 표시됩니다</p>
            </div>
          </div>
        </div>
      </div>
    </main>
  </div>
</template>

<script>
export default { name: 'ManualPage' }
</script>

<script setup>
import { ref, onMounted, nextTick } from 'vue'
import { storeToRefs } from 'pinia'
import { useTheme } from '../composables/useTheme.js'
import { useManualStore } from '../stores/manualStore.js'
import ChecklistReview from '../components/manual/ChecklistReview.vue'
import { analyzeManual, refineManual, confirmManual, registerZones, fetchZones } from '../api/manuals.js'

/* ── Theme ── */
const { isDark, toggle: toggleTheme } = useTheme()

/* ── Store ── */
const store = useManualStore()
const { docFiles, uploadError, zoneFile, csvError, registeredZones } = storeToRefs(store)
const checklist = store.checklist
const zoneRegister = store.zoneRegister

/* ── UI-only state ── */
const isDragging = ref(false)
const isCsvDragging = ref(false)
const dropTarget = ref(null)
const editingZone = ref(null)
const editingType = ref(null)
const editingIndex = ref(null)
const editText = ref('')

/* ── Utilities ── */
function formatSize(bytes) {
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
  return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
}

function downloadSample() {
  const a = document.createElement('a')
  a.href = '/zones_sample.xlsx'
  a.download = 'zones_sample.xlsx'
  a.click()
}

/* ── Drag: checklist → zone ── */
function onDragStart(e, item) {
  e.dataTransfer.setData('text/plain', item)
  e.dataTransfer.effectAllowed = 'copy'
}

function onDropToZone(e, zone, type) {
  dropTarget.value = null
  const text = e.dataTransfer.getData('text/plain')?.trim()
  if (!text || zone[type].includes(text)) return
  zone[type].push(text)
}

/* ── CSV Zone Upload ── */
const CSV_MAX = 5 * 1024 * 1024

function validateCsv(file) {
  if (!file.name.match(/\.(csv|xlsx)$/i)) return 'CSV 또는 XLSX 파일만 허용됩니다'
  if (file.size > CSV_MAX) return '파일 크기는 5MB 이하여야 합니다'
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

async function loadRegisteredZones() {
  try { registeredZones.value = await fetchZones(null) } catch { registeredZones.value = [] }
}

async function onRegisterZones() {
  zoneRegister.loading = true
  zoneRegister.error = ''
  try {
    await registerZones(zoneFile.value, null)
    await loadRegisteredZones()
    zoneFile.value = null
  } catch (e) {
    const detail = e?.response?.data?.detail
    zoneRegister.error = typeof detail === 'string' ? detail : '구역 등록에 실패했습니다.'
  } finally {
    zoneRegister.loading = false
  }
}

onMounted(() => {
  if (registeredZones.value.length === 0) loadRegisteredZones()
})

/* ── PDF Upload ── */
const PDF_MAX = 20 * 1024 * 1024

function validatePdf(file) {
  if (!file.name.match(/\.pdf$/i)) return `${file.name}: PDF 파일만 허용됩니다`
  if (file.size > PDF_MAX) return `${file.name}: 파일 크기는 20MB 이하여야 합니다`
  return null
}

function handlePdfFiles(fileList) {
  uploadError.value = ''
  for (const file of Array.from(fileList)) {
    const err = validatePdf(file)
    if (err) { uploadError.value = err; return }
    if (!docFiles.value.some(f => f.name === file.name && f.size === file.size)) {
      docFiles.value.push(file)
    }
  }
}

function onFileChange(e) {
  if (e.target.files.length) handlePdfFiles(e.target.files)
  e.target.value = ''
}

function onDrop(e) {
  isDragging.value = false
  if (e.dataTransfer.files.length) handlePdfFiles(e.dataTransfer.files)
}

/* ── Analysis ── */
async function onAnalyze() {
  if (!docFiles.value.length) return
  checklist.loading = true
  checklist.error = ''
  checklist.saved = false
  checklist.zoneSaved = false
  checklist.sessionId = ''
  checklist.static = []
  checklist.dynamic = []
  checklist.staticCategories = []
  checklist.dynamicCategories = []
  checklist.zones = []
  try {
    const result = await analyzeManual(docFiles.value, null)
    checklist.sessionId = result.session_id
    checklist.static = result.static || []
    checklist.dynamic = result.dynamic || []
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
    else checklist.error = `Analysis failed. (${e?.response?.status ?? 'network'}) Please try again.`
  } finally {
    checklist.loading = false
  }
}

async function onRefine({ feedback }) {
  if (!feedback) return
  checklist.loading = true
  checklist.error = ''
  try {
    const result = await refineManual(checklist.sessionId, feedback, null)
    checklist.static = result.static || []
    checklist.dynamic = result.dynamic || []
  } catch {
    checklist.error = 'Regeneration failed. Keeping previous results.'
  } finally {
    checklist.loading = false
  }
}

async function onConfirm({ sessionId, static: staticItems, dynamic: dynamicItems }) {
  checklist.loading = true
  checklist.error = ''
  try {
    await confirmManual(
      sessionId,
      staticItems,
      dynamicItems,
      checklist.zones,
      checklist.staticCategories,
      checklist.dynamicCategories,
      null,
    )
    checklist.saved = true
    checklist.zoneSaved = false
    store.zoneViewLoaded = false
  } catch {
    checklist.error = 'Save failed. Please try again.'
  } finally {
    checklist.loading = false
  }
}

async function onConfirmZones() {
  checklist.loading = true
  checklist.zoneError = ''
  checklist.zoneSaved = false
  try {
    await confirmManual(
      checklist.sessionId,
      checklist.static,
      checklist.dynamic,
      checklist.zones,
      checklist.staticCategories,
      checklist.dynamicCategories,
      null,
    )
    checklist.zoneSaved = true
    store.zoneViewLoaded = false
  } catch {
    checklist.zoneError = 'Save failed. Please try again.'
  } finally {
    checklist.loading = false
  }
}

/* ── Zone Item Editing ── */
function startEdit(zoneName, type, index, text) {
  editingZone.value = zoneName
  editingType.value = type
  editingIndex.value = index
  editText.value = text
  nextTick(() => {
    const inputs = document.querySelectorAll('.edit-input')
    const last = inputs[inputs.length - 1]
    if (last) last.focus()
  })
}

function saveEdit() {
  if (!editingZone.value || !editingType.value || editingIndex.value === null) return
  const zone = checklist.zones.find(z => z.zone === editingZone.value)
  if (zone) zone[editingType.value][editingIndex.value] = editText.value.trim()
  cancelEdit()
}

function cancelEdit() {
  editingZone.value = null
  editingType.value = null
  editingIndex.value = null
  editText.value = ''
}

function removeItem(zoneName, type, index) {
  const zone = checklist.zones.find(z => z.zone === zoneName)
  if (zone) zone[type].splice(index, 1)
}

function addItem(zoneName, type) {
  const zone = checklist.zones.find(z => z.zone === zoneName)
  if (zone) {
    zone[type].push('')
    startEdit(zoneName, type, zone[type].length - 1, '')
  }
}
</script>

<style scoped>
/* ═══════════════════════════ Design System ═══════════════════════════ */
.app-shell {
  --c-bg: #f9fafb;
  --c-bg-card: #ffffff;
  --c-bg-elevated: #f3f4f6;
  --c-border: #e5e7eb;
  --c-border-light: #f0f0f0;
  --c-text: #111827;
  --c-text-secondary: #4b5563;
  --c-text-muted: #9ca3af;
  --c-accent: #77942e;
  --c-accent-soft: #eef2df;
  --c-accent-border: #b6c77a;
  --c-accent-hover: #64731e;
  --c-red: #ef4444;
  --c-red-soft: #fef2f2;
  --c-green: #22c55e;
  --c-green-soft: #f0fdf4;
}

.app-shell.dark {
  --c-bg: #111827;
  --c-bg-card: #1a1f2e;
  --c-bg-elevated: #1f2937;
  --c-border: #2d3548;
  --c-border-light: #263040;
  --c-text: #f3f4f6;
  --c-text-secondary: #9ca3af;
  --c-text-muted: #6b7280;
  --c-accent-soft: #263112;
  --c-accent-border: #4d6420;
  --c-red-soft: #2d1215;
  --c-green-soft: #122a1a;
}

/* ═══════════════════════════ Base ═══════════════════════════ */
.app-shell {
  min-height: 100vh;
  background: var(--c-bg);
  color: var(--c-text);
  font-family: 'Pretendard Variable', Pretendard, -apple-system, BlinkMacSystemFont, system-ui, sans-serif;
  font-size: 14px;
  line-height: 1.5;
  transition: background 0.3s, color 0.3s;
  -webkit-font-smoothing: antialiased;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

button { font-family: inherit; cursor: pointer; white-space: nowrap; }
input, textarea { font-family: inherit; }
i { display: inline-flex; align-items: center; justify-content: center; }

/* ═══════════════════════════ Top Nav ═══════════════════════════ */
.topnav {
  position: sticky; top: 0; z-index: 50;
  background: var(--c-bg-card);
  border-bottom: 1px solid var(--c-border-light);
  backdrop-filter: blur(12px);
}
.topnav-inner {
  max-width: 1440px; margin: 0 auto; padding: 0 24px;
  min-height: 64px; display: flex; align-items: center; justify-content: space-between;
}
.topnav-brand { display: flex; align-items: center; gap: 8px; }
.brand-logo-icon { height: 30px; object-fit: contain; }
.brand-logo-text { height: 20px; object-fit: contain; }
.profile-nav-btn {
  display: flex; align-items: center; justify-content: center;
  width: 40px; height: 40px; border-radius: 50%;
  color: var(--c-accent-hover); text-decoration: none;
  background: var(--c-accent-soft);
  border: 1px solid var(--c-accent-border);
  box-shadow: 0 4px 12px rgba(17, 24, 39, 0.06);
  transition: transform 0.15s, box-shadow 0.15s, background 0.15s;
}
.profile-nav-btn:hover { transform: translateY(-1px); background: color-mix(in srgb, var(--c-accent-soft) 78%, white); box-shadow: 0 8px 18px rgba(17, 24, 39, 0.08); }
.profile-nav-btn i { font-size: 18px; }
.brand-icon {
  width: 32px; height: 32px; border-radius: 10px;
  background: var(--c-accent); display: flex; align-items: center; justify-content: center;
  flex-shrink: 0;
}
.brand-icon i { color: #fff; font-size: 16px; }
.brand-text { display: flex; flex-direction: column; }
.brand-title { font-size: 13px; font-weight: 700; color: var(--c-text); line-height: 1; }
.brand-sub { font-size: 10px; color: var(--c-text-muted); line-height: 1; margin-top: 1px; }

.topnav-actions { display: flex; align-items: center; gap: 12px; }
.topnav-actions-only { margin-left: auto; }
.topnav-links { display: flex; gap: 4px; }
.nav-link {
  font-size: 12px; padding: 6px 12px; border-radius: 8px;
  color: var(--c-text-secondary); text-decoration: none; font-weight: 500;
  transition: all 0.15s;
}
.nav-link:hover { color: var(--c-text); background: var(--c-bg-elevated); }
.nav-link.active { background: var(--c-accent-soft); color: var(--c-accent-hover); font-weight: 600; }
.nav-divider { width: 1px; height: 20px; background: var(--c-border); }

.theme-toggle {
  width: 40px; height: 40px; border-radius: 10px; border: 1px solid var(--c-border);
  background: var(--c-bg-elevated); display: flex; align-items: center; justify-content: center;
  transition: all 0.2s;
}
.theme-toggle:hover { background: var(--c-border); }
.theme-toggle i { font-size: 18px; color: var(--c-text-secondary); }

/* ═══════════════════════════ Main Content ═══════════════════════════ */
.main-content { max-width: 1440px; margin: 0 auto; padding: 24px; }

.page-header { display: flex; align-items: center; gap: 8px; margin-bottom: 20px; }
.page-header-icon {
  width: 28px; height: 28px; border-radius: 8px;
  background: var(--c-accent-soft); display: flex; align-items: center; justify-content: center;
}
.page-header-icon i { color: var(--c-accent-hover); font-size: 14px; }
.page-title { font-size: 18px; font-weight: 700; color: var(--c-text); }
.page-desc { font-size: 12px; color: var(--c-text-muted); margin-left: 8px; }

/* ═══════════════════════════ Card Layout ═══════════════════════════ */
.card-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 16px; }
.card-row-bottom { height: calc(100vh - 340px); min-height: 480px; }

.card {
  background: var(--c-bg-card); border: 1px solid var(--c-border-light);
  border-radius: 14px; padding: 20px; transition: background 0.3s, border 0.3s;
}
.card-glow {
  position: relative; overflow: hidden;
}
.card-glow::before {
  content: ''; position: absolute; inset: 0; pointer-events: none;
  background: radial-gradient(ellipse at 50% 0%, rgba(132,204,22,0.05) 0%, transparent 70%);
}
.card-scroll { display: flex; flex-direction: column; padding: 0; overflow: hidden; }

.card-sticky-header { padding: 20px 20px 12px; flex-shrink: 0; }
.card-scroll-body { flex: 1; overflow-y: auto; padding: 0 20px 20px; }

.card-header-row { display: flex; align-items: center; justify-content: space-between; }
.card-title { font-size: 14px; font-weight: 600; color: var(--c-text); }
.card-title.mb { margin-bottom: 4px; }
.card-hint { font-size: 12px; color: var(--c-text-muted); margin-bottom: 16px; line-height: 1.5; }

/* ═══════════════════════════ Buttons ═══════════════════════════ */
.btn-accent {
  font-size: 12px; padding: 6px 16px; border-radius: 10px; border: none;
  background: var(--c-accent); color: #fff; font-weight: 600;
  transition: all 0.2s; flex-shrink: 0;
}
.btn-accent:hover:not(:disabled) { background: var(--c-accent-hover); }
.btn-accent:disabled { opacity: 0.5; cursor: not-allowed; }

.btn-accent-soft {
  font-size: 12px; padding: 6px 12px; border-radius: 8px;
  background: var(--c-accent-soft); color: var(--c-accent-hover);
  border: 1px solid var(--c-accent-border); display: flex; align-items: center; gap: 6px;
  transition: all 0.2s;
}
.btn-accent-soft:hover { filter: brightness(0.95); }

.btn-ghost {
  font-size: 11px; padding: 6px 12px; border-radius: 8px; border: 1px solid var(--c-border);
  background: var(--c-bg-elevated); color: var(--c-text-secondary);
  display: flex; align-items: center; gap: 5px; transition: all 0.2s;
}
.btn-ghost:hover { background: var(--c-border); }
.btn-ghost i { font-size: 12px; }

.btn-analyze {
  width: 100%; padding: 10px; border-radius: 12px; border: none;
  font-size: 14px; font-weight: 600; transition: all 0.2s;
}
.btn-analyze:disabled { background: var(--c-bg-elevated); color: #9ca3af; cursor: not-allowed; }
.btn-analyze-ready:not(:disabled) { background: var(--c-accent); color: #fff; }
.btn-analyze-ready:not(:disabled):hover { background: var(--c-accent-hover); }

.btn-refine {
  width: 100%; padding: 8px; border-radius: 8px; border: 1px solid var(--c-border);
  background: var(--c-bg-elevated); color: var(--c-text-secondary);
  font-size: 12px; font-weight: 500; display: flex; align-items: center; justify-content: center; gap: 5px;
  transition: all 0.2s;
}
.btn-refine:hover { background: var(--c-border); }

.btn-remove { background: none; border: none; color: var(--c-text-muted); font-size: 14px; flex-shrink: 0; padding: 2px; transition: color 0.15s; }
.btn-remove:hover { color: var(--c-red); }

.btn-icon-done { background: none; border: none; color: var(--c-accent); font-size: 12px; padding: 2px; }
.btn-icon-cancel { background: none; border: none; color: var(--c-text-muted); font-size: 12px; padding: 2px; }
.btn-icon-cancel:hover { color: var(--c-text-secondary); }
.btn-delete-hover { background: none; border: none; color: var(--c-text-muted); font-size: 13px; padding: 2px; opacity: 0; transition: all 0.15s; flex-shrink: 0; }
.btn-add-item {
  font-size: 12px; color: var(--c-accent-hover); background: none; border: none;
  display: flex; align-items: center; gap: 4px; font-weight: 500; padding: 2px 0; transition: color 0.15s;
}
.btn-add-item:hover { color: var(--c-accent); }

/* ═══════════════════════════ Dropzone ═══════════════════════════ */
.dropzone {
  display: flex; align-items: center; gap: 8px; padding: 8px;
  border: 2px dashed var(--c-border); border-radius: 10px;
  margin-bottom: 12px; transition: all 0.2s;
}
.dropzone-active { border-color: var(--c-accent-border); background: var(--c-accent-soft); }
.dropzone-hint { font-size: 11px; color: var(--c-text-muted); }
.hidden-input { display: none; }

/* ═══════════════════════════ File List ═══════════════════════════ */
.file-chip {
  display: flex; align-items: center; gap: 8px; padding: 8px 12px;
  background: var(--c-accent-soft); border: 1px solid var(--c-accent-border);
  border-radius: 10px; margin-bottom: 12px;
}
.file-chip-name { font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; font-weight: 500; color: var(--c-text); }
.check-icon { color: var(--c-accent); font-size: 13px; flex-shrink: 0; }

.file-list { display: flex; flex-direction: column; gap: 6px; }
.file-item {
  display: flex; align-items: center; gap: 10px; padding: 8px 12px;
  background: var(--c-bg-elevated); border: 1px solid var(--c-border);
  border-radius: 10px;
}
.pdf-icon { color: var(--c-accent); font-size: 14px; flex-shrink: 0; }
.file-name { font-size: 12px; flex: 1; overflow: hidden; text-overflow: ellipsis; font-weight: 500; color: var(--c-text); }
.file-size { font-size: 10px; color: var(--c-text-muted); font-family: 'JetBrains Mono', monospace; flex-shrink: 0; }

.empty-drop {
  padding: 20px; text-align: center; border: 1px dashed var(--c-border);
  border-radius: 10px; background: var(--c-bg-elevated);
}
.empty-drop-icon { font-size: 22px; color: var(--c-text-muted); margin-bottom: 8px; }
.empty-drop p { font-size: 12px; color: var(--c-text-muted); }

/* ═══════════════════════════ Zone Tags ═══════════════════════════ */
.zone-tags { display: flex; flex-wrap: wrap; gap: 6px; }
.zone-tag {
  font-size: 11px; padding: 4px 10px; border-radius: 999px;
  background: var(--c-accent-soft); color: var(--c-accent-hover);
  border: 1px solid var(--c-accent-border); font-weight: 500;
}
.empty-hint { font-size: 12px; color: var(--c-text-muted); font-style: italic; }

/* ═══════════════════════════ Error / Success ═══════════════════════════ */
.error-text { font-size: 12px; color: var(--c-red); font-weight: 500; margin-bottom: 8px; }
.error-box { padding: 12px; border-radius: 10px; background: var(--c-red-soft); border: 1px solid rgba(239,68,68,0.2); margin-bottom: 12px; }
.error-box p { font-size: 12px; color: var(--c-red); font-weight: 500; }
.success-box {
  padding: 12px; border-radius: 10px; background: var(--c-green-soft); border: 1px solid rgba(34,197,94,0.2);
  margin-bottom: 12px; text-align: center; font-size: 12px; color: var(--c-green); font-weight: 500;
  display: flex; align-items: center; justify-content: center; gap: 6px;
}
.success-hint { font-size: 12px; color: var(--c-green); font-weight: 500; margin-top: 4px; display: flex; align-items: center; gap: 4px; }

/* ═══════════════════════════ Spinner ═══════════════════════════ */
.spinner-text { display: flex; align-items: center; gap: 6px; }
.spinner {
  display: inline-block; width: 14px; height: 14px;
  border: 2px solid rgba(255,255,255,0.3); border-top-color: #fff;
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
.spinner-accent {
  display: inline-block; width: 32px; height: 32px;
  border: 3px solid var(--c-accent-soft); border-top-color: var(--c-accent);
  border-radius: 50%; animation: spin 0.8s linear infinite;
}
.spinner-light { border-color: rgba(255,255,255,0.3); border-top-color: #fff; }
@keyframes spin { to { transform: rotate(360deg); } }

/* ═══════════════════════════ Checklist ═══════════════════════════ */
.drag-hint {
  font-size: 11px; color: var(--c-text-muted); margin-bottom: 10px;
  display: flex; align-items: center; gap: 4px;
}
.checklist-label {
  font-size: 10px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.05em;
  color: var(--c-text-muted); margin-bottom: 8px; display: inline-block;
}
.checklist-sections { display: flex; flex-direction: column; gap: 16px; }
.checklist-group { display: flex; flex-direction: column; gap: 4px; }
.checklist-item {
  display: flex; align-items: center; gap: 10px; padding: 8px 12px;
  background: var(--c-bg-elevated); border: 1px solid var(--c-border);
  border-radius: 10px; cursor: grab; transition: all 0.15s; user-select: none;
}
.checklist-item:hover { border-color: var(--c-text-muted); }
.checklist-item:active { cursor: grabbing; opacity: 0.7; }
.checklist-item input[type="checkbox"] {
  width: 16px; height: 16px; border-radius: 4px; accent-color: var(--c-accent); cursor: pointer; flex-shrink: 0;
}
.checklist-item span { font-size: 12px; color: var(--c-text); flex: 1; }
.drag-handle { font-size: 14px; color: var(--c-text-muted); flex-shrink: 0; opacity: 0; transition: opacity 0.15s; }
.checklist-item:hover .drag-handle { opacity: 1; }

/* ═══════════════════════════ Refine Panel ═══════════════════════════ */
.refine-panel {
  margin-top: 12px; padding: 12px; border-radius: 10px;
  background: var(--c-bg-elevated); border: 1px solid var(--c-border);
}
.refine-panel textarea {
  width: 100%; padding: 10px; border-radius: 8px; border: 1px solid var(--c-border);
  background: var(--c-bg-card); color: var(--c-text); font-size: 12px;
  resize: none; outline: none; transition: border 0.2s;
}
.refine-panel textarea:focus { border-color: var(--c-accent-border); }
.refine-panel textarea::placeholder { color: var(--c-text-muted); }
.refine-actions { display: flex; align-items: center; justify-content: space-between; margin-top: 8px; }
.char-count { font-size: 10px; color: var(--c-text-muted); }
.refine-btns { display: flex; gap: 8px; }

/* ═══════════════════════════ Loading Center ═══════════════════════════ */
.loading-center { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 40px 0; gap: 12px; }
.loading-center p { font-size: 12px; color: var(--c-text-muted); }
.empty-center { display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 32px 0; }
.empty-center-icon { font-size: 22px; color: var(--c-text-muted); margin-bottom: 8px; }
.empty-center p { font-size: 12px; color: var(--c-text-muted); text-align: center; }

/* ═══════════════════════════ Zone Cards ═══════════════════════════ */
.zone-list { display: flex; flex-direction: column; gap: 12px; }
.zone-card {
  padding: 16px; border-radius: 12px;
  background: var(--c-bg-elevated); border: 1px solid var(--c-border);
}
.zone-card-header { display: flex; align-items: center; gap: 8px; margin-bottom: 12px; }
.zone-icon-box {
  width: 24px; height: 24px; border-radius: 6px;
  background: var(--c-accent-soft); display: flex; align-items: center; justify-content: center; flex-shrink: 0;
}
.zone-icon-box i { color: var(--c-accent-hover); font-size: 12px; }
.zone-name { font-size: 13px; font-weight: 600; color: var(--c-text); }

.zone-section { margin-bottom: 12px; }
.zone-section:last-child { margin-bottom: 0; }

.zone-items { display: flex; flex-direction: column; gap: 4px; padding: 4px; border-radius: 8px; transition: all 0.2s; border: 2px solid transparent; min-height: 32px; }
.zone-items.drop-target-active { border-color: var(--c-accent-border); background: var(--c-accent-soft); }
.drop-hint { font-size: 11px; color: var(--c-accent-hover); text-align: center; padding: 4px 0; }
.zone-item-row { display: flex; align-items: center; }

.edit-inline { flex: 1; display: flex; align-items: center; gap: 4px; }
.edit-input {
  flex: 1; padding: 6px 10px; border-radius: 6px; border: 1px solid var(--c-accent-border);
  background: var(--c-bg-card); color: var(--c-text); font-size: 12px; outline: none;
}

.zone-item-display {
  flex: 1; display: flex; align-items: center;
}
.zone-item-display:hover .btn-delete-hover { opacity: 1; }
.zone-item-text {
  flex: 1; padding: 6px 10px; border-radius: 6px; font-size: 12px;
  background: var(--c-bg-card); border: 1px solid var(--c-border);
  color: var(--c-text); cursor: pointer; transition: all 0.15s;
}
.zone-item-text:hover { border-color: var(--c-accent-border); color: var(--c-text); }

/* ═══════════════════════════ Scrollbar ═══════════════════════════ */
.card-scroll-body::-webkit-scrollbar { width: 4px; }
.card-scroll-body::-webkit-scrollbar-track { background: transparent; }
.card-scroll-body::-webkit-scrollbar-thumb { background: var(--c-border); border-radius: 999px; }
.card-scroll-body::-webkit-scrollbar-thumb:hover { background: var(--c-text-muted); }

/* ═══════════════════════════ Responsive ═══════════════════════════ */
@media (max-width: 1024px) {
  .card-row { grid-template-columns: 1fr; }
  .card-row-bottom { height: auto; min-height: auto; }
  .topnav-links { display: none; }
  .nav-divider { display: none; }
}
</style>
