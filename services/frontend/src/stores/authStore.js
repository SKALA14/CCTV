// src/stores/authStore.js
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { getMe, login as apiLogin, logout as apiLogout } from '../api/auth.js'

export const useAuthStore = defineStore('auth', () => {
    const user        = ref(null)   // { user_id, username, role, site_id, site_name, must_change_password }
    const initialized = ref(false)

    const isLoggedIn    = computed(() => user.value !== null)
    const isAdmin       = computed(() => user.value?.role === 'admin')
    const mustChangePwd = computed(() => user.value?.must_change_password === true)

    async function fetchMe() {
        try {
            const res  = await getMe()
            user.value = res.data
        } catch {
            user.value = null
        } finally {
            initialized.value = true
        }
    }

    async function login(username, password) {
        const res  = await apiLogin(username, password)
        user.value = res.data
    }

    async function logout() {
        try { await apiLogout() } catch { /* 서버 오류여도 클라이언트 상태 초기화 */ }
        user.value = null
    }

    return { user, isLoggedIn, isAdmin, mustChangePwd, initialized, fetchMe, login, logout }
})
