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
