<!-- 클립 상세 페이지 — 이벤트 로드 후 ClipDetail 렌더 -->
<template>
  <div class="clip-view">
    <!-- Loading -->
    <div v-if="loading" class="state-center">
      <span class="spinner"></span>
      <p>Loading clip data...</p>
    </div>

    <!-- Error -->
    <div v-else-if="error" class="error-box">
      <i class="ri-error-warning-line"></i>
      <div>
        <p class="error-title">Failed to load clip</p>
        <p class="error-detail">{{ error }}</p>
        <button class="btn-retry" @click="loadEvent(props.id)">다시 시도</button>
      </div>
    </div>

    <!-- Not Found -->
    <div v-else-if="!event" class="state-center">
      <i class="ri-file-warning-line" style="font-size: 32px; opacity: 0.4;"></i>
      <p>Clip not found.</p>
      <button class="btn-retry" @click="router.replace({ name: 'search' })">
        <i class="ri-arrow-left-line"></i> Back to Search
      </button>
    </div>

    <!-- ClipDetail Component -->
    <ClipDetail
      v-else
      :key="props.id"
      :event="event"
      :related-events="relatedEvents"
    />
  </div>
</template>

<script setup>
import { ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { storeToRefs } from 'pinia'
import ClipDetail from '../components/search/ClipDetail.vue'
import { fetchEventById } from '../api/events.js'
import { useEventStore } from '../stores/eventStore.js'
import { DUMMY_MODE } from '../constants/mode.js'
import { DUMMY_EVENTS } from '../constants/dummyData.js'

const props = defineProps({ id: String })
const router = useRouter()

const { lastSearchResults } = storeToRefs(useEventStore())
const relatedEvents = lastSearchResults

const event = ref(null)
const loading = ref(false)
const error = ref(null)

async function loadEvent(id) {
  if (!id) return
  if (DUMMY_MODE) {
    event.value = DUMMY_EVENTS.find(e => e.id === id) ?? null
    return
  }
  loading.value = true
  error.value = null
  try {
    event.value = await fetchEventById(id)
  } catch (e) {
    if (e.response?.status === 404) {
      router.replace({ name: 'search' })
      return
    }
    error.value = e.response?.data?.detail ?? e.message
  } finally {
    loading.value = false
  }
}

watch(() => props.id, loadEvent, { immediate: true })
</script>

<style scoped>
.clip-view {
  padding: 16px;
  min-height: 100%;
}

.state-center {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  padding: 80px 0;
  gap: 12px;
  color: var(--text-muted);
  font-size: 13px;
}

.spinner {
  display: inline-block;
  width: 32px;
  height: 32px;
  border: 3px solid var(--track-bg);
  border-top-color: var(--green);
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }

.error-box {
  display: flex;
  align-items: flex-start;
  gap: 12px;
  padding: 16px;
  margin: 16px 0;
  border-radius: 12px;
  background: rgba(239, 68, 68, 0.05);
  border: 1px solid rgba(239, 68, 68, 0.2);
}
.error-box i { color: #ef4444; font-size: 18px; margin-top: 1px; flex-shrink: 0; }
.error-title { font-size: 13px; font-weight: 600; color: #ef4444; margin: 0 0 4px; }
.error-detail { font-size: 12px; color: #ef4444; opacity: 0.8; margin: 0 0 8px; }

.btn-retry {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 5px 12px;
  border-radius: 7px;
  border: 1px solid rgba(239, 68, 68, 0.3);
  background: transparent;
  color: #ef4444;
  font-size: 12px;
  cursor: pointer;
  transition: background 0.15s;
}
.btn-retry:hover { background: rgba(239, 68, 68, 0.08); }
</style>
