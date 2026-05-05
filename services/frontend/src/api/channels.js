import api from './index.js'
import { DUMMY_MODE } from '../constants/mode.js'

export async function postChannel({ slot, camera_id, name, url, options }) {
    if (DUMMY_MODE) return
    await api.post('/channels', { slot, camera_id, name, url, options })
}

export async function deleteChannel(camera_id) {
    if (DUMMY_MODE) return
    await api.delete(`/channels/${camera_id}`)
}
