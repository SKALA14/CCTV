import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/authStore.js'
import DashboardView      from '../views/DashboardView.vue'
import SearchView         from '../views/SearchView.vue'
import ClipDetailView     from '../views/ClipDetailView.vue'
import ManualView         from '../views/ManualView.vue'
import LoginView          from '../views/LoginView.vue'
import AdminView          from '../views/AdminView.vue'
import PasswordChangeView from '../views/PasswordChangeView.vue'
import StatusView         from '../views/StatusView.vue'
import SettingsView       from '../views/SettingsView.vue'

const routes = [
    { path: '/login',           name: 'login',           component: LoginView,          meta: { public: true } },
    { path: '/',                name: 'dashboard',        component: DashboardView },
    { path: '/search',          name: 'search',           component: SearchView },
    { path: '/search/:id',      name: 'clip-detail',      component: ClipDetailView,    props: true },
    { path: '/manual',          name: 'manual',           component: ManualView },
    { path: '/admin',           name: 'admin',            component: AdminView,          meta: { superadminOnly: true } },
    { path: '/status',          name: 'status',           component: StatusView,         meta: { superadminOnly: true } },
    { path: '/password-change', name: 'password-change',  component: PasswordChangeView },
    { path: '/settings',        name: 'settings',         component: SettingsView },
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

// 네비게이션 가드 — 비인증 접근 차단
router.beforeEach(async (to) => {
    if (to.meta.public) return true

    const auth = useAuthStore()

    if (!auth.initialized) {
        await auth.fetchMe()
    }

    if (!auth.isLoggedIn) {
        return { name: 'login' }
    }

    // 비밀번호 변경 강제: /password-change 외 모든 페이지 차단
    if (auth.mustChangePwd && to.name !== 'password-change') {
        return { name: 'password-change' }
    }

    // superadmin 전용 페이지
    if (to.meta.superadminOnly && !auth.isSuperadmin) {
        return { name: 'dashboard' }
    }

    return true
})

export default router
