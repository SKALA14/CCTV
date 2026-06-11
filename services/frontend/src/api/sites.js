import api from './index.js'

// 현장은 설치 시 seed로 등록 — 조회만 제공.
export const getSites = ()       => api.get('/sites').then(r => r.data)
export const getSite  = (siteId) => api.get(`/sites/${siteId}`).then(r => r.data)
