import { DUMMY_MODE } from '../constants/mode.js'
import api from './index.js'

const STORAGE_KEY = 'cctv_manuals'

export async function fetchManuals() {
  if (DUMMY_MODE) return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
  return api.get('/manuals').then(r => r.data)
}

export async function uploadManual(file) {
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
  return api.post('/manuals', form).then(r => r.data)
}

export async function deleteManual(id) {
  if (DUMMY_MODE) {
    const list = JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]')
    localStorage.setItem(STORAGE_KEY, JSON.stringify(list.filter(f => f.id !== id)))
    return
  }
  return api.delete(`/manuals/${id}`)
}

export async function analyzeManual(file) {
  if (DUMMY_MODE) {
    return {
      session_id: crypto.randomUUID(),
      static: ['소화기 비치 위치가 접근 불가 상태로 차단됨', '안전 통로에 장애물이 방치됨'],
      dynamic: ['작업자가 바닥에 쓰러지거나 낙상하는 상황', 'PPE 미착용 상태로 작업 중인 상황'],
    }
  }
  const form = new FormData()
  form.append('file', file)
  // gpt-4o 3단계 호출이므로 90초 타임아웃 적용
  return api.post('/manuals/analyze', form, { timeout: 90000 }).then(r => r.data)
}

export async function refineManual(sessionId, feedback) {
  if (DUMMY_MODE) {
    return {
      session_id: sessionId,
      static: ['피드백 반영된 static 항목'],
      dynamic: ['피드백 반영된 dynamic 항목'],
    }
  }
  return api.post('/manuals/refine', { session_id: sessionId, feedback }).then(r => r.data)
}

export async function confirmManual(sessionId, staticItems, dynamicItems) {
  if (DUMMY_MODE) return { status: 'saved' }
  return api.post('/manuals/confirm', {
    session_id: sessionId,
    static: staticItems,
    dynamic: dynamicItems,
  }).then(r => r.data)
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
