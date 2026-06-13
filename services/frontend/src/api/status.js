import api from './index.js'

export const getOverview    = () => api.get('/status/overview').then(r => r.data)
export const getDevices     = () => api.get('/status/devices').then(r => r.data)
export const getAccounts    = () => api.get('/status/accounts').then(r => r.data)
export const getTodayEvents = (zone) => api.get('/status/today-events', { params: zone ? { zone } : {} }).then(r => r.data)
export const getHealth      = () => api.get('/status/health').then(r => r.data)
