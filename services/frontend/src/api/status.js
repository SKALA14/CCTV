import api from './index.js'

export const getOverview = () => api.get('/status/overview').then(r => r.data)
export const getDevices  = () => api.get('/status/devices').then(r => r.data)
export const getAccounts = () => api.get('/status/accounts').then(r => r.data)
export const getTodayEvents = (siteId) => api.get(`/status/sites/${siteId}/today-events`).then(r => r.data)
