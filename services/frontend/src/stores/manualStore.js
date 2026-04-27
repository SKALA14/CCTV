import { defineStore } from 'pinia'
import { ref } from 'vue'
import { fetchManuals, uploadManual, deleteManual } from '../api/manuals.js'

export const useManualStore = defineStore('manual', () => {
  const files = ref([])
  const loading = ref(false)

  async function load() {
    loading.value = true
    files.value = await fetchManuals()
    loading.value = false
  }

  async function upload(file) {
    const meta = await uploadManual(file)
    files.value.unshift(meta)
  }

  async function remove(id) {
    await deleteManual(id)
    files.value = files.value.filter(f => f.id !== id)
  }

  return { files, loading, load, upload, remove }
})
