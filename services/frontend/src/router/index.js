import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '../stores/authStore.js'
import DashboardView  from '../views/DashboardView.vue'
import SearchView     from '../views/SearchView.vue'
import ClipDetailView from '../views/ClipDetailView.vue'
import ManualView     from '../views/ManualView.vue'
import LoginView      from '../views/LoginView.vue'
import SettingsView   from '../views/SettingsView.vue'

const routes = [
    { path: '/login', name: 'login', component: LoginView, meta: { public: true } },
    { path: '/',      name: 'dashboard',   component: DashboardView },
    { path: '/search', name: 'search',     component: SearchView },
    {
        path: '/search/:id',
        name: 'clip-detail',
        component: ClipDetailView,
        props: true,
    },
    { path: '/manual',   name: 'manual',   component: ManualView },
    { path: '/settings', name: 'settings', component: SettingsView },
]

const router = createRouter({
    history: createWebHistory(),
    routes,
})

// 네비게이션 가드 — 비인증 접근 차단
router.beforeEach(async (to) => {
    if (to.meta.public) return true  // 로그인 페이지는 항상 허용

    const auth = useAuthStore()

    // 아직 인증 상태를 모르면 서버에서 확인 (한 번만 실행)
    if (!auth.initialized) {
        await auth.fetchMe()
    }

    if (!auth.isLoggedIn) {
        return { name: 'login' }
    }

    return true
})

export default router
