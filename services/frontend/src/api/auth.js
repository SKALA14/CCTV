// 인증 API — 로그인·로그아웃·내 정보 조회
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
