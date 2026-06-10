import api from './index.js'

export const getUsers         = (siteId)              => api.get(`/sites/${siteId}/users`).then(r => r.data)
export const createUser       = (siteId, data)         => api.post(`/sites/${siteId}/users`, data).then(r => r.data)
export const updateUser       = (siteId, userId, data) => api.patch(`/sites/${siteId}/users/${userId}`, data).then(r => r.data)
export const deleteUser       = (siteId, userId)       => api.delete(`/sites/${siteId}/users/${userId}`)
export const resetPassword    = (siteId, userId)       => api.post(`/sites/${siteId}/users/${userId}/reset-password`).then(r => r.data)
export const changeMyPassword = (data)                 => api.patch('/users/me/password', data)
