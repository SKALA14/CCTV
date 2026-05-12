import api from './index.js'
import { DUMMY_MODE } from '../constants/mode.js'

export async function getChannels() {
    if (DUMMY_MODE) return { data: [] }
    return api.get('/channels')
}

export async function postChannel({ slot, name, channelName, rtspUrl, sourceType, description, options }) {
    if (DUMMY_MODE) return
    await api.post('/channels', { slot, name, channelName, rtspUrl, sourceType, description, options })
}

export async function putChannel(channelName, patch) {
    if (DUMMY_MODE) return
    await api.put(`/channels/${channelName}`, patch)
}

export async function deleteChannel(channelName) {
    if (DUMMY_MODE) return
    await api.delete(`/channels/${channelName}`)
}
