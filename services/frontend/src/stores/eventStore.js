import { defineStore } from 'pinia'
import { ref } from 'vue'
import { TOAST_DURATION } from '../constants/events.js'

export const useEventStore = defineStore('event', () => {
    const liveEvents = ref([])
    const toastQueue = ref([])

    function pushLiveEvent(event) {
        liveEvents.value.unshift(event)
        toastQueue.value.push(event)
        setTimeout(() => {
            toastQueue.value.shift()
        }, TOAST_DURATION)
    }

    const lastSearchResults = ref([])
    function setSearchResults(results) {
        lastSearchResults.value = results
    }

    return { liveEvents, toastQueue, pushLiveEvent, lastSearchResults, setSearchResults }
})