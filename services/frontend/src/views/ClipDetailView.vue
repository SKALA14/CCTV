<template>
  <div class="p-4">
    <div v-if="loading" class="flex justify-center items-center h-64">
      <div class="w-8 h-8 border-4 border-blue-500 border-t-transparent rounded-full animate-spin"></div>
    </div>
    <div v-else-if="error" class="text-[#dc2626] text-center py-8 text-sm">{{ error }}</div>
    <ClipDetail
      v-else-if="event"
      :event="event"
      :related-events="relatedEvents"
    />
  </div>
</template>

<script setup>
import { ref, onMounted } from 'vue'
import { storeToRefs } from 'pinia'
import ClipDetail from '../components/search/ClipDetail.vue'
import { fetchEventById } from '../api/events.js'
import { useEventStore } from '../stores/eventStore.js'
import { DUMMY_MODE } from '../constants/mode.js'
import { DUMMY_EVENTS } from '../constants/dummyData.js'

const props = defineProps({ id: String })

const { lastSearchResults } = storeToRefs(useEventStore())
const relatedEvents = lastSearchResults

const event = ref(null)
const loading = ref(false)
const error = ref(null)

onMounted(async () => {
  if (DUMMY_MODE) {
    event.value = DUMMY_EVENTS.find(e => e.id === props.id) ?? null
    return
  }
  loading.value = true
  try {
    event.value = await fetchEventById(props.id)
  } catch (e) {
    error.value = e.message
  } finally {
    loading.value = false
  }
})
</script>
