import api from './index.js'

export const getSites   = ()                    => api.get('/sites').then(r => r.data)
export const getSite    = (siteId)              => api.get(`/sites/${siteId}`).then(r => r.data)
export const createSite = (name)                => api.post('/sites', { name }).then(r => r.data)
export const updateSite = (siteId, name)        => api.patch(`/sites/${siteId}`, { name }).then(r => r.data)
export const deleteSite = (siteId)              => api.delete(`/sites/${siteId}`)
