import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchManuals, uploadManual, deleteManual } from '../api/manuals.js'

export const useManualStore = defineStore('manual', () => {
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

  return { files, loading, load, upload, remove }
})
