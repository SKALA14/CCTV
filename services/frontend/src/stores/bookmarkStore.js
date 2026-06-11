// src/stores/bookmarkStore.js
// 즐겨찾기(후속조치) — 운영자가 중요한 이벤트를 북마크. 1차는 localStorage 기반(백엔드 무관).
import { defineStore } from 'pinia'
import { ref } from 'vue'

const STORAGE_KEY = 'cctv_bookmarks'

function _load() {
  try { return JSON.parse(localStorage.getItem(STORAGE_KEY) || '[]') } catch { return [] }
}

export const useBookmarkStore = defineStore('bookmark', () => {
  const items = ref(_load())   // [{ event_id, camera_name, danger_level, description, occurred_at, thumbnail_url, saved_at }]

  function _persist() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items.value))
  }

  function isBookmarked(eventId) {
    return items.value.some(b => b.event_id === eventId)
  }

  function toggle(event) {
    const id = event.event_id || event.id
    const idx = items.value.findIndex(b => b.event_id === id)
    if (idx >= 0) {
      items.value.splice(idx, 1)
    } else {
      items.value.unshift({
        event_id: id,
        camera_name: event.camera_name || event.channel_id || '',
        danger_level: event.danger_level || 'none',
        description: event.description || event.reason || '',
        occurred_at: event.occurred_at || event.timestamp || new Date().toISOString(),
        thumbnail_url: event.thumbnail_url || (event.snapshot_urls && event.snapshot_urls[0]) || null,
        saved_at: new Date().toISOString(),
      })
    }
    _persist()
  }

  function remove(eventId) {
    items.value = items.value.filter(b => b.event_id !== eventId)
    _persist()
  }

  return { items, isBookmarked, toggle, remove }
})
