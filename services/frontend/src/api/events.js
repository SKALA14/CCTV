import api from './index.js'

export const fetchEvents = (params = {}) =>
    api.get('/events', { params }).then(r => r.data)

export const fetchEventById = (id) =>
    api.get(`/events/${id}`).then(r => r.data)

export const searchEvents = (
  query,
  channelId     = null,
  startDate     = null,
  endDate       = null,
  skipTimeParse = false,
  siteId        = null,
) =>
    api.get('/events/search', {
        params: {
            q:               query,
            channel_id:      channelId,
            start_date:      startDate,
            end_date:        endDate,
            skip_time_parse: skipTimeParse || undefined,
            site_id:         siteId        || undefined,
        },
    }).then(r => r.data)