// 매뉴얼 API — 파일·체크리스트·구역·PDF 분석 호출
import { DUMMY_MODE } from '../constants/mode.js'
import api from './index.js'

const STORAGE_KEY = 'cctv_manuals'

export async function fetchManuals(siteId = null) {
  if (DUMMY_MODE) return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  const q = siteId ? `?site_id=${encodeURIComponent(siteId)}` : ''
  return api.get(`/manuals${q}`).then(r => r.data)
}

// siteId: 보통 null — 백엔드가 현재 사용자의 현장을 사용.
function _siteQuery(siteId) {
  return siteId ? `?site_id=${encodeURIComponent(siteId)}` : ''
}

export async function uploadManual(file, siteId = null) {
  if (DUMMY_MODE) {
    const meta = {
      id: crypto.randomUUID(),
      name: file.name,
      size: file.size,
      uploaded_at: new Date().toISOString(),
      type: file.type,
    }
    const list = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    list.unshift(meta)
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list))
    return meta
  }
  const form = new FormData()
  form.append('file', file)
  return api.post(`/manuals${_siteQuery(siteId)}`, form).then(r => r.data)
}

export async function deleteManual(id, siteId = null) {
  if (DUMMY_MODE) {
    const list = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list.filter(f => f.id !== id)))
    return
  }
  return api.delete(`/manuals/${id}${_siteQuery(siteId)}`)
}

export async function analyzeManual(files, siteId = null) {
  if (DUMMY_MODE) {
    return {
      session_id: crypto.randomUUID(),
      static: ['소화기 비치 위치가 접근 불가 상태로 차단됨', '안전 통로에 장애물이 방치됨'],
      dynamic: ['작업자가 바닥에 쓰러지거나 낙상하는 상황', 'PPE 미착용 상태로 작업 중인 상황'],
      zones: [],
    }
  }
  const form = new FormData()
  const fileList = Array.isArray(files) ? files : [files]
  fileList.forEach(f => form.append('files', f))
  return api.post(`/manuals/analyze${_siteQuery(siteId)}`, form, { timeout: 120000 }).then(r => r.data)
}

export async function refineManual(sessionId, feedback, siteId = null) {
  if (DUMMY_MODE) {
    return {
      session_id: sessionId,
      static: ['피드백 반영된 static 항목'],
      dynamic: ['피드백 반영된 dynamic 항목'],
    }
  }
  return api.post(`/manuals/refine${_siteQuery(siteId)}`, { session_id: sessionId, feedback }).then(r => r.data)
}

export async function confirmManual(sessionId, staticItems, dynamicItems, zones = [], staticCategories = [], dynamicCategories = [], siteId = null) {
  if (DUMMY_MODE) return { status: 'saved' }
  return api.post(`/manuals/confirm${_siteQuery(siteId)}`, {
    session_id: sessionId,
    static: staticItems,
    dynamic: dynamicItems,
    static_categories: staticCategories,
    dynamic_categories: dynamicCategories,
    zones,
  }).then(r => r.data)
}

export async function registerZones(zonesFile, siteId = null) {
  if (DUMMY_MODE) return { status: 'saved', zones: ['크레인 작업구역', '용접 작업구역'] }
  const form = new FormData()
  form.append('zones_file', zonesFile)
  return api.post(`/manuals/zones${_siteQuery(siteId)}`, form).then(r => r.data)
}

export async function fetchZones(siteId = null) {
  if (DUMMY_MODE) return ['크레인 작업구역', '용접 작업구역', '고소 작업구역']
  const q = siteId ? `?site_id=${encodeURIComponent(siteId)}` : ''
  return api.get(`/manuals/zones${q}`).then(r => r.data)
}

export async function fetchChecklist(siteId = null) {
  if (DUMMY_MODE) return { static: '', dynamic: '', zones: [] }
  const q = siteId ? `?site_id=${encodeURIComponent(siteId)}` : ''
  return api.get(`/manuals/checklist${q}`).then(r => r.data)
}

export async function analyzeDiff(file, siteId = null) {
  if (DUMMY_MODE) {
    return {
      static: { added: ['새로 추가된 static 항목?'], removed_candidates: [] },
      dynamic: { added: [], removed_candidates: ['사라진 dynamic 항목?'] },
    }
  }
  const form = new FormData()
  form.append('file', file)
  return api.post(`/manuals/analyze-diff${_siteQuery(siteId)}`, form, { timeout: 120000 }).then(r => r.data)
}

export async function mergeChecklist(payload, siteId = null) {
  if (DUMMY_MODE) return { status: 'merged' }
  return api.post(`/manuals/merge${_siteQuery(siteId)}`, payload).then(r => r.data)
}


export async function analyzeInstruction(cameraId, text) {
  if (DUMMY_MODE) {
    return {
      camera_id: cameraId,
      static: ['지게차 주차구역 외 주차 상태'],
      dynamic: ['보행자가 지게차 동선에 진입하는 상황'],
    }
  }
  return api.post(`/channels/${cameraId}/instruction/analyze`, { text }).then(r => r.data)
}

export async function confirmInstruction(cameraId, staticItems, dynamicItems) {
  if (DUMMY_MODE) return { status: 'saved' }
  return api.patch(`/channels/${cameraId}/instruction/confirm`, {
    static: staticItems,
    dynamic: dynamicItems,
  }).then(r => r.data)
}
