// src/api/auth.js
import api from './index.js'

export async function login(username, password) {
    return api.post('/auth/login', { username, password })
}

export async function logout() {
    return api.post('/auth/logout')
}

export async function getMe() {
    return api.get('/auth/me')
}
