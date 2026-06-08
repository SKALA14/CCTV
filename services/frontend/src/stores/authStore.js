// src/stores/authStore.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getMe, login as apiLogin, logout as apiLogout } from '../api/auth.js'

export const useAuthStore = defineStore('auth', () => {
    const user = ref(null)   // { username, role } 또는 null
    const initialized = ref(false)  // fetchMe() 가 한 번 이상 실행됐는지 여부

    const isLoggedIn = computed(() => user.value !== null)
    const isAdmin    = computed(() => user.value?.role === 'admin')

    // 앱 초기화 시 서버에서 현재 로그인 상태 확인
    async function fetchMe() {
        try {
            const res = await getMe()
            user.value = res.data
        } catch {
            user.value = null
        } finally {
            initialized.value = true
        }
    }

    async function login(username, password) {
        const res = await apiLogin(username, password)
        user.value = res.data   // { username, role }
    }

    async function logout() {
        try { await apiLogout() } catch { /* 서버 오류여도 클라이언트 상태는 초기화 */ }
        user.value = null
    }

    return { user, isLoggedIn, isAdmin, initialized, fetchMe, login, logout }
})
