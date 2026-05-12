<template>
  <div class="p-4 max-w-3xl mx-auto">
    <div class="mb-4 space-y-3">
      <SearchBar @search="handleSearch" />
      <ChannelFilter
        :channels="channels"
        v-model="selectedChannelId"
      />
    </div>
    <ResultList
      :events="events"
      :loading="loading"
      :error="error"
    />
  </div>
</template>

<script setup>
import { ref, computed, watch, onMounted } from 'vue'
import SearchBar from '../components/search/SearchBar.vue'
import ChannelFilter from '../components/search/ChannelFilter.vue'
import ResultList from '../components/search/ResultList.vue'
import { useEvents } from '../composables/useEvents.js'
import { useChannels } from '../composables/useChannels.js'
import { useEventStore } from '../stores/eventStore.js'

const { events, loading, error, load, search } = useEvents()
const { slots } = useChannels()
const channels = computed(() => slots.value.filter(Boolean))
const eventStore = useEventStore()

onMounted(() => { load() })

const selectedChannelId = ref(null)
const lastQuery = ref('')

async function handleSearch(query) {
  lastQuery.value = query
  await search(query, selectedChannelId.value)
  eventStore.setSearchResults(events.value)
}

watch(selectedChannelId, async () => {
  if (lastQuery.value) {
    await search(lastQuery.value, selectedChannelId.value)
  } else {
    const params = selectedChannelId.value ? { channel_id: selectedChannelId.value } : {}
    await load(params)
  }
  eventStore.setSearchResults(events.value)
})
</script>
