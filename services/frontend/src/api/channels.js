import api from './index.js'
import { DUMMY_MODE } from '../constants/mode.js'

export async function getChannels(siteId = null) {
    if (DUMMY_MODE) return { data: [] }
    const q = siteId ? `?site_id=${encodeURIComponent(siteId)}` : ''
    return api.get(`/channels${q}`)
}

export async function postChannel({ slot, name, channelName, rtspUrl, sourceType, description, options, zone }) {
    if (DUMMY_MODE) return
    await api.post('/channels', { slot, name, channelName, rtspUrl, sourceType, description, options, zone })
}

export async function putChannel(channelName, patch) {
    if (DUMMY_MODE) return
    await api.put(`/channels/${channelName}`, patch)
}

export async function deleteChannel(channelName) {
    if (DUMMY_MODE) return
    await api.delete(`/channels/${channelName}`)
}
