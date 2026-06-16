// 매뉴얼 전역 상태 — 업로드 파일 목록
import { defineStore } from 'pinia'
import { ref, reactive } from 'vue'
import { fetchManuals, uploadManual, deleteManual } from '../api/manuals.js'

export const useManualStore = defineStore('manual', () => {
  // ── 업로드된 파일 목록 ──────────────────────────────────────
  const files = ref([])
  const loading = ref(false)

  async function load(siteId = null) {
    loading.value = true
    try {
      files.value = await fetchManuals(siteId)
    } catch {
      files.value = []
    } finally {
      loading.value = false
    }
  }

  async function upload(file, siteId = null) {
    const meta = await uploadManual(file, siteId)
    files.value.unshift(meta)
  }

  async function remove(id, siteId = null) {
    await deleteManual(id, siteId)
    files.value = files.value.filter(f => f.id !== id)
  }

  // ── ManualView 세션 상태 (탭 이동 후에도 유지) ───────────────
  const docFiles = ref([])
  const uploadError = ref('')
  const zoneFile = ref(null)
  const csvError = ref('')
  const registeredZones = ref([])
  const zoneRegister = reactive({ loading: false, error: '' })
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
    zoneSaved: false,
    zoneError: '',
  })

  // ── ZoneView 데이터 (탭 이동 후에도 유지) ───────────────────
  const zoneViewData = ref([])
  const zoneViewLoaded = ref(false)

  return {
    files, loading, load, upload, remove,
    docFiles, uploadError,
    zoneFile, csvError,
    registeredZones, zoneRegister,
    checklist,
    zoneViewData, zoneViewLoaded,
  }
})
