import api from './index.js'

export const fetchEvents = (params = {}) =>
    api.get('/events', { params }).then(r => r.data)

export const fetchEventById = (id) =>
    api.get(`/events/${id}`).then(r => r.data)

export const searchEvents = (query, channelId = null) =>
    api.get('/events/search', { params: { q: query, channel_id: channelId } }).then(r => r.data)